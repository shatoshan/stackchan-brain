FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# 顔検出モデル（OpenCV Zoo YuNet 2023mar）。sha256 で固定
RUN python -c "import hashlib, urllib.request; \
url='https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'; \
data=urllib.request.urlopen(url).read(); \
assert hashlib.sha256(data).hexdigest()=='8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'; \
open('/app/face_detection_yunet_2023mar.onnx','wb').write(data)"
COPY *.py ./
CMD ["python", "-u", "main.py"]
