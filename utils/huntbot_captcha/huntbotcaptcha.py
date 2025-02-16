# This project is inspired by PhanDat's project https://github.com/realphandat/phandat-selfbot. Some of the original code has been taken and added to it. We thank him for this work.
# LICENSE: https://web.archive.org/web/20241125182749/https://github.com/realphandat/phandat-selfbot/blob/main/LICENSE


import os, io, sys, json, subprocess

# check req libs
required_modules = {
    "python-socketio": "socketio",
    "aiohttp": "aiohttp",
    "numpy": "numpy",
    "pillow": "PIL",
}


def install_packages(packages):
    for pip_name, import_name in packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"{pip_name} was not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])


install_packages(required_modules)


import socketio, aiohttp, glob, numpy
from PIL import Image


script_dir = os.path.dirname(__file__)
config_path = os.path.join(script_dir, "../../config.json")
with open(config_path, "r") as f:
    config = json.load(f)


socketport = config["socket"]["port"]


sio = socketio.AsyncServer()
app = aiohttp.web.Application()
sio.attach(app)


class HuntBotCaptchaSolver:
    async def solve_huntbot_captcha(self, captcha_url):
        checks = []
        check_images = glob.glob(
            os.path.join(script_dir, "letters/**/*.png"), recursive=True
        )

        for check_image in sorted(check_images):
            img = Image.open(check_image)
            checks.append((img, img.size, check_image.split(".")[0].split(os.sep)[-1]))

        async with aiohttp.ClientSession() as session:
            async with session.get(captcha_url) as resp:
                large_image = Image.open(io.BytesIO(await resp.read()))
                large_array = numpy.array(large_image)

        matches = []
        for img, (small_w, small_h), letter in checks:
            small_array = numpy.array(img)
            mask = small_array[:, :, 3] > 0
            for y in range(large_array.shape[0] - small_h + 1):
                for x in range(large_array.shape[1] - small_w + 1):
                    segment = large_array[y : y + small_h, x : x + small_w]
                    if numpy.array_equal(segment[mask], small_array[mask]):
                        if not any(
                            (m[0] - small_w < x < m[0] + small_w)
                            and (m[1] - small_h < y < m[1] + small_h)
                            for m in matches
                        ):
                            matches.append((x, y, letter))
        matches = sorted(matches, key=lambda tup: tup[0])
        return "".join([i[2] for i in matches])


@sio.event
async def captcha(sid, captcha_url):
    print(f"CAPTCHA URL recieved: {captcha_url}")
    solver = HuntBotCaptchaSolver()
    try:
        result = await solver.solve_huntbot_captcha(captcha_url)
        print(f"Solved CAPTCHA: {result}")
        await sio.emit("captcha_solution", result, to=sid)
    except Exception as e:
        print(f"CAPTCHA solve error: {e}")
        await sio.emit("captcha_solution", f"ERROR: {e}", to=sid)


if __name__ == "__main__":
    aiohttp.web.run_app(app, port=socketport)
