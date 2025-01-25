
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
from PIL import Image
import numpy as np


class Hunyuan3DImageTo3D:
    @classmethod
    def INPUT_TYPES(s):
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
                "paint": ("BOOLEAN",  {"default": False}),
            }
        }
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename",)
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
    def install_check():
        this_path = os.path.dirname(os.path.realpath(__file__))
        if importlib.util.find_spec('custom_rasterizer') is None:
            print("Installing custom_rasterizer")
            Hunyuan3DImageTo3D.popen_print_output(
                [sys.executable, 'setup.py', 'install'],
                os.path.join(
                    this_path,
                    'Hunyuan3D-2/hy3dgen/texgen/custom_rasterizer'
                )
            )

        if importlib.util.find_spec('hy3dgen') is None:
            print("Installing hy3dgen")
            Hunyuan3DImageTo3D.popen_print_output(
                [sys.executable, 'setup.py', 'install'],
                os.path.join(this_path, 'Hunyuan3D-2')
                )

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
    def get_spare_filename(filename_format):
        for i in range(1, 10000):
            filename = filename_format.format(random.randint(0, 0x100000))
            if not os.path.exists(filename):
                return filename
        return None

    def process(
        self, image,
        mask,
        steps,
        floater_remover,
        face_remover,
        face_reducer,
        paint,
    ):
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        import hy3dgen.shapegen

        output_dir = folder_paths.get_output_directory()
        output_3d_file = None
        with tempfile.TemporaryDirectory() as temp_dir:
            for img, mask1 in zip(image, mask):
                i = 255. * img.cpu().numpy()
                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                if mask1 is not None:
                    m = 255. * mask1.cpu().numpy()
                    mask = Image.fromarray(m)
                    mask = np.clip(mask, 0, 255).astype(np.uint8)
                    mask = 255 - mask
                    img.putalpha(Image.fromarray(mask, mode='L'))
                input_image_file = os.path.join(temp_dir, "input.png")
                img.save(input_image_file)

                mask = i = img = None

                model_path = 'tencent/Hunyuan3D-2'
                pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(model_path)  # noqa: E501

                output_3d_file = Hunyuan3DImageTo3D.get_spare_filename(
                    os.path.join(output_dir, 'hunyuan3d_{:05X}.glb')
                )
                mesh = pipeline(
                    image=input_image_file, num_inference_steps=steps,
                    generator=torch.manual_seed(2025))[0]
                if floater_remover:
                    mesh = hy3dgen.shapegen.FloaterRemover()(mesh)
                if face_remover:
                    mesh = hy3dgen.shapegen.DegenerateFaceRemover()(mesh)
                if face_reducer:
                    mesh = hy3dgen.shapegen.FaceReducer()(mesh)

                if paint:
                    from hy3dgen.texgen import Hunyuan3DPaintPipeline
                    pipeline = Hunyuan3DPaintPipeline.from_pretrained(model_path)  # noqa: E501
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
    ):
        m = hashlib.sha256()
        m.update(steps)
        m.update(floater_remover)
        m.update(face_remover)
        m.update(face_reducer)
        m.update(paint)
        return m.digest().hex()
