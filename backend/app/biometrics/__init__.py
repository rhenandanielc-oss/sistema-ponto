import os

# Limite de pixels por imagem decodificada pelo OpenCV (padrão dele: 1 gigapixel ≈ 3 GB de
# memória). Um PNG de 400 KB pode declarar 20000 x 20000 pixels; com este limite ele é recusado
# antes de alocar.
# Precisa ser definido antes do primeiro `import cv2` (o OpenCV lê o valor uma única vez).
MAX_IMAGE_PIXELS = 4096 * 4096
os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = str(MAX_IMAGE_PIXELS)
