
This custom node might fail after the first restart.  Restart ComfyUI again.  Click on the panel ~~□~~ to look for errors.

## Status

* I haven't tried the "paint" option yet.  I don't have a big enough computer to run it, somebody tell me if it does or does not work.

## If it doesn't install...

### Suse

Hunyuan-3D needs g++ 13, Suse has g++ 14+ by default

`sudo zypper install g++-13`

### Install from git

You need to get the submodules if you install from git

```
cd custom_nodes
git clone https://github.com/niknah/ComfyUI-Hunyuan-3D-2
cd ComfyUI-Hunyuan-3D-2
git submodule update --init
```

## Usage...

* When you run it for the first time it will download the models which will take a long time.
* Press the panel button on the top right ~~□~~ to see the progress.
* Put the input image into the "input" folder.  The 3D .glb file is saved in "output"


* Hunyuan-3D-2 uses more main memory than GPU memory.  On a 16gb RAM main memory computer, you'll have to quit everything else other than ComfyUI, have only a few custom\_nodes installed.  I have ran it on 16gb RAM, 8gb VRAM without paint.
