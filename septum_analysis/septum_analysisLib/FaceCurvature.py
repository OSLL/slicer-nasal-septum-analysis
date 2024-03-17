from slicer.util import pip_install


try:
    import cv2
except:
    pip_install('opencv-python')
    import cv2

try:
    import numpy as np
except:
    pip_install('numpy')
    import numpy as np


def analyze_face_curvature(images: cv2.Mat):
    result = []
    result1 = []
    for data in images:
        try:
            data = cv2.bilateralFilter(data, 3, 75, 75)
            _, thresh = cv2.threshold(data, data.mean(), 255, cv2.THRESH_TOZERO)
            cont, _ = cv2.findContours(thresh, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_SIMPLE)

            if len(cont)==0:
                result.append(0)
                result1.append(0)
                continue

            maxc = max(enumerate(cont), key=lambda x: cv2.contourArea(x[1]))[0]

            ch = cv2.convexHull(cont[maxc], returnPoints=False)
            ch_ = cv2.convexHull(cont[maxc])

            t1 = sum(map(lambda x: x[0][3], cv2.convexityDefects(cont[maxc], ch)))
            t2 = cv2.contourArea(ch_) - cv2.contourArea(cont[maxc])
            result.append(t1)
            result1.append(t2)
        except Exception as e:
            print(e)
            if len(result)==0:
                result.append(0)
                result1.append(0)
            result.append(result[-1])
            result1.append(result1[-1])
    return result, result1