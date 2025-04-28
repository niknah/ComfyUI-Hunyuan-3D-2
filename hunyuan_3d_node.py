
import glob
import tempfile
import folder_paths
import importlib.util
import subprocess
import sys
import os
import random
import torch
import hashlib
import platform
import re
from packaging import version
from PIL import Image
import numpy as np


class Hunyuan3DImageTo3D:
    @classmethod
    def INPUT_TYPES(s):
        models = [
            'tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0',
            'tencent/Hunyuan3D-2/hunyuan3d-dit-v2-0-fast',
            'tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini',
            'tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini-fast',
            'tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini-turbo',
            'tencent/Hunyuan3D-2mv/hunyuan3d-dit-v2-mv-fast',
            'tencent/Hunyuan3D-2mv/hunyuan3d-dit-v2-mv-turbo',
            'tencent/Hunyuan3D-2mv/hunyuan3d-dit-v2-mv',
            ]
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "mask": ("MASK",),
                "steps": ("INT", {"default": 30}),
                "floater_remover": ("BOOLEAN", {"default": True}),
                "face_remover": ("BOOLEAN", {"default": True}),
                "face_reducer": ("BOOLEAN",  {"default": True}),
                "paint": ("BOOLEAN",  {
                    "default": False,
                    "tooltip": "Paint needs a lot more VRAM",
                }),
                "model": (models, {
                    "tooltip": "huggingface id of model(author/name/subfolder)",  # noqa: E501
                }),
                "back_image": ("IMAGE",),
                "back_mask": ("MASK",),
                "left_image": ("IMAGE",),
                "left_mask": ("MASK",),
                "right_image": ("IMAGE",),
                "right_mask": ("MASK",),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model file",)
    FUNCTION = "process"
    CATEGORY = "3d"

    @staticmethod
    def popen_print_output(args, cwd=None, shell=False):
        process = subprocess.Popen(
            args,
            cwd=cwd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            )
        stdout, stderr = process.communicate()
        print(
            f"exit code: {process.returncode}, {' '.join(args)}\n"
            f"stdout: {stdout.decode('utf-8')}\n"
            f"stderr: {stderr.decode('utf-8')}\n"
            "\n"
            )

    @staticmethod
    def install_custom_rasterizer(this_path):
        print("Installing custom_rasterizer")
        Hunyuan3DImageTo3D.popen_print_output(
            [sys.executable, 'setup.py', 'install'],
            os.path.join(
                this_path,
                'Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer'
            )
        )

    @staticmethod
    def install_hy3dgen(this_path):
        print("Installing hy3dgen")
        Hunyuan3DImageTo3D.popen_print_output(
            [sys.executable, 'setup.py', 'install'],
            os.path.join(this_path, 'Hunyuan3D-2')
            )

    @staticmethod
    def install_mesh_processor(this_path):
        renderer_dir = os.path.join(
            this_path,
            'Hunyuan3D-2/hy3dgen/texgen/differentiable_renderer'
        )
        if platform.system() == 'Windows':
            if importlib.util.find_spec('mesh_processor') is None:
                print("Installing mesh_processor")
                Hunyuan3DImageTo3D.popen_print_output(
                    [sys.executable, 'setup.py', 'install'],
                    renderer_dir
                    )
        else:  # Linux
            if len(glob.glob(f'{renderer_dir}/mesh_processor*.so')) == 0:
                Hunyuan3DImageTo3D.popen_print_output(
                    ['/bin/bash', 'compile_mesh_painter.sh'],
                    renderer_dir
                    )

    @staticmethod
    def install_check():
        print("install check")
        this_path = os.path.dirname(os.path.realpath(__file__))

        if not os.path.exists(
            os.path.join(this_path, 'Hunyuan3D-2/README.md')
        ):
            try:
                import pygit2
                repo_path = os.path.join(os.path.dirname(__file__))
                repo = pygit2.Repository(repo_path)
                submodules = pygit2.submodules.SubmoduleCollection(repo)
                submodules.update(init=True)
            except Exception as e:
                print(f"pygit2 failed: {e}")
#            Hunyuan3DImageTo3D.popen_print_output(
#                ['git', 'submodule', 'update', '--init', '--recursive'],
#                this_path,
#                shell=True,
#            )

        cr_version = version.parse("0.1")
        if importlib.util.find_spec('custom_rasterizer') is None:
            Hunyuan3DImageTo3D.install_custom_rasterizer(this_path)
        elif cr_version > version.parse(importlib.metadata.version('custom_rasterizer')):  # noqa: E501
            Hunyuan3DImageTo3D.install_custom_rasterizer(this_path)

        hy3dgen_version = version.parse("2.0.2")
        # Don't know why.  setup.py doesn't remove the previous version
        Hunyuan3DImageTo3D.popen_print_output(
            ['pip', 'uninstall', 'hy3dgen-2.0.0-py3.12.egg']
        )
        if importlib.util.find_spec('hy3dgen') is None:
            Hunyuan3DImageTo3D.install_hy3dgen(this_path)
        elif hy3dgen_version > version.parse(importlib.metadata.version('hy3dgen')):  # noqa: E501
            Hunyuan3DImageTo3D.install_hy3dgen(this_path)

        if importlib.util.find_spec('mesh_processor') is None:
            Hunyuan3DImageTo3D.install_mesh_processor(this_path)

    @staticmethod
    def get_spare_filename(filename_format):
        for i in range(1, 10000):
            filename = filename_format.format(random.randint(0, 0x100000))
            if not os.path.exists(filename):
                return filename
        return None

    def comfy_img_to_file(self, image, mask, input_image_file):
        i = 255. * image.cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        if mask is not None:
            m = 255. * mask.cpu().numpy()
            mask_pil = Image.fromarray(m)
            mask_pil = np.clip(mask_pil, 0, 255).astype(np.uint8)
            mask_pil = 255 - mask_pil
            # If it crashes here,
            # check that you have transparency in the image
            img.putalpha(Image.fromarray(mask_pil, mode='L'))
        img.save(input_image_file)

    def process(
        self, image,
        mask,
        steps,
        floater_remover,
        face_remover,
        face_reducer,
        paint,
        model='tencent/Hunyuan3D-2',
        back_image=None,
        back_mask=None,
        left_image=None,
        left_mask=None,
        right_image=None,
        right_mask=None,
    ):
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        import hy3dgen.shapegen

        output_dir = folder_paths.get_output_directory()
        checkpoint_dir = os.path.join(
            folder_paths.get_folder_paths('checkpoints')[0],
            'Hunyuan3D-2'
        )
        if not os.path.exists(checkpoint_dir):
            os.mkdir(checkpoint_dir)

# Not working
#        if 'HY3DGEN_MODELS' not in os.environ:
#            os.environ['HY3DGEN_MODELS'] = checkpoint_dir

        variant = 'fp16'
        variant_m = re.match(r"^(.*)\[variant=([^\]]+)\]$", model)
        if variant_m is not None:
            model = variant_m.group(1)
            variant = variant_m.group(2)

        subfolder = None
        subfolder_m = re.match(r"^([^/]+/[^/]+)/(.+)$", model)
        if subfolder_m is not None:
            model = subfolder_m.group(1)
            subfolder = subfolder_m.group(2)

        isMV = model == 'tencent/Hunyuan3D-2mv'
        output_3d_file = None
        with tempfile.TemporaryDirectory() as temp_dir:
            nth = 0
            front_images_list = []
            back_images_list = []
            left_images_list = []
            right_images_list = []
            if image is not None:
                front_images_list = list(zip(image, mask))
            if back_image is not None:
                back_images_list = list(zip(back_image, back_mask))
            if left_image is not None:
                left_images_list = list(zip(left_image, left_mask))
            if right_image is not None:
                right_images_list = list(zip(right_image, right_mask))

            max_len = max(
                len(front_images_list),
                len(back_images_list),
                len(left_images_list),
                len(right_images_list),
            )

            sides = {
                'front': front_images_list,
                'back': back_images_list,
                'left': left_images_list,
                'right': right_images_list,
            }

            # front should always be first
            side_names = [
                'front',
                'back',
                'left',
                'right',
            ]

            for nth in range(0, max_len):
                image_obj = None
                for side in side_names:
                    side_list = sides[side]
                    if side_list is None:
                        continue

                    if nth >= len(side_list):
                        continue

                    side_info = side_list[nth]
                    if side_info is None:
                        continue

                    (side_image, side_mask) = side_list[nth]
                    input_image_file = os.path.join(
                        temp_dir, f"{side}{nth}.png"
                        )
                    self.comfy_img_to_file(
                        side_image, side_mask, input_image_file
                        )
                    image_obj = {}
                    if isMV:
                        image_obj[side] = input_image_file
                    else:
                        image_obj = input_image_file
                        break

                pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                    model,
                    subfolder=subfolder,
                    variant=variant
                )

                output_3d_file = Hunyuan3DImageTo3D.get_spare_filename(
                    os.path.join(output_dir, 'hunyuan3d_{:05X}.glb')
                )

                mesh = pipeline(
                    image=image_obj, num_inference_steps=steps,
                    generator=torch.manual_seed(2025)
                )[0]
                if floater_remover:
                    mesh = hy3dgen.shapegen.FloaterRemover()(mesh)
                if face_remover:
                    mesh = hy3dgen.shapegen.DegenerateFaceRemover()(mesh)
                if face_reducer:
                    mesh = hy3dgen.shapegen.FaceReducer()(mesh)

                if paint:
                    from hy3dgen.texgen import Hunyuan3DPaintPipeline
                    pipeline = Hunyuan3DPaintPipeline.from_pretrained(
                        "tencent/Hunyuan3D-2",
                        # model,
                    )
                    mesh = pipeline(mesh, image=input_image_file)

                mesh.export(output_3d_file)
                break
        print(os.path.basename(output_3d_file))
        return (os.path.basename(output_3d_file), )

    @classmethod
    def IS_CHANGED(
        self, image, mask,
        steps,
        floater_remover,
        face_remover,
        face_reducer,
        paint,
        model,
        back_image,
        back_mask,
        left_image,
        left_mask,
        right_image,
        right_mask,
    ):
        m = hashlib.sha256()
        m.update(image)
        m.update(mask)
        m.update(steps)
        m.update(floater_remover)
        m.update(face_remover)
        m.update(face_reducer)
        m.update(paint)
        m.update(model)
        m.update(back_image)
        m.update(back_mask)
        m.update(left_image)
        m.update(left_mask)
        m.update(right_image)
        m.update(right_mask)
        return m.digest().hex()
