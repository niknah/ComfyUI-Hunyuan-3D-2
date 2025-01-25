
from .hunyuan_3d_node import Hunyuan3DImageTo3D

Hunyuan3DImageTo3D.install_check()

NODE_CLASS_MAPPINGS = {
    "Hunyuan3D2ImageTo3D": Hunyuan3DImageTo3D
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Hunyuan3D2ImageTo3D": "Hunyuan3D-2 Image to 3D"
}
