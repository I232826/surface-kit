# Howdy recorder for the Surface Pro 7 IR camera (ov7251 on the IPU4P).
#
# Reads the capture node directly instead of going through libcamera, which puts
# the gain back to 1x on every stream start. Frames come out of the kernel as
# 10-bit in 16-bit words and the sensor is mounted a quarter turn off, so each
# one is scaled to 8 bits, turned upright and handed over as BGR like any other
# Howdy recorder.
import subprocess

import cv2
import numpy as np

SENSOR = "ov7251 2-0060"
CSI2 = "Intel IPU6 CSI2 1"
CAPTURE = "Intel IPU6 ISYS Capture 8"
WIDTH, HEIGHT = 640, 480
FRAME_BYTES = WIDTH * HEIGHT * 2
# About 4x, measured on a face at 40 cm with the emitter on
GAIN = 64


def _run(*args):
	return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def _node(media, entity):
	return _run("media-ctl", "-d", media, "-e", entity).strip()


class surface_ir_reader:
	def __init__(self, media="/dev/media0"):
		self.media = media
		self.proc = None
		self.frames = 0

	def _start(self):
		ml = lambda *a: _run("media-ctl", "-d", self.media, *a)
		ml("-l", f'"{CSI2}":1 -> "{CAPTURE}":0[1]')
		ml("-V", f'"{SENSOR}":0 [fmt:Y10_1X10/{WIDTH}x{HEIGHT}]')
		ml("-V", f'"{CSI2}":0 [fmt:Y10_1X10/{WIDTH}x{HEIGHT}]')
		ml("-V", f'"{CSI2}":1 [fmt:Y10_1X10/{WIDTH}x{HEIGHT}]')
		video = _node(self.media, CAPTURE)
		_run("v4l2-ctl", "-d", _node(self.media, SENSOR), "--set-ctrl", f"analogue_gain={GAIN}")
		self.proc = subprocess.Popen(
			["v4l2-ctl", "-d", video, f"--set-fmt-video=width={WIDTH},height={HEIGHT},pixelformat=Y10 ",
			 "--stream-mmap", "--stream-to=-"],
			stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

	def isOpened(self):
		return self.proc is not None and self.proc.poll() is None

	def get(self, prop):
		# Sizes as seen after the quarter turn
		if prop == cv2.CAP_PROP_FRAME_WIDTH:
			return HEIGHT
		if prop == cv2.CAP_PROP_FRAME_HEIGHT:
			return WIDTH
		return 0

	def set(self, prop, value):
		return False

	def grab(self):
		ret, _ = self.read()
		return ret

	def read(self):
		if self.proc is None:
			self._start()
		raw = self.proc.stdout.read(FRAME_BYTES)
		if raw is None or len(raw) != FRAME_BYTES:
			return False, None
		self.frames += 1
		frame = np.frombuffer(raw, dtype="<u2").reshape(HEIGHT, WIDTH)
		frame = np.clip(frame >> 2, 0, 255).astype(np.uint8)
		frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
		return True, cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

	def release(self):
		if self.proc is not None:
			self.proc.terminate()
			try:
				self.proc.wait(timeout=5)
			except subprocess.TimeoutExpired:
				self.proc.kill()
				self.proc.wait()
			self.proc.stdout.close()
			self.proc = None
