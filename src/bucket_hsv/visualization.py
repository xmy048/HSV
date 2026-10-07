"""绘制颜色区域质心。十字不表示桶口中心。"""
import cv2

PALETTE = {"red": (0, 0, 255), "yellow": (0, 255, 255), "blue": (255, 120, 0)}


def render_detections(image, result):
    output = image.copy()
    height, width = output.shape[:2]
    # 字体缩放仅影响标注，不改变图像尺寸或检测坐标。
    scale = max(0.45, min(width, height) / 1000.0)
    thickness = max(1, round(scale * 2))
    for index, detection in enumerate(result.detections):
        color = PALETTE[detection.color]
        if index < len(result.contours):
            cv2.drawContours(output, result.contours[index], -1, color, thickness)
        center = (round(detection.center_x), round(detection.center_y))
        cv2.drawMarker(output, center, color, cv2.MARKER_CROSS,
                       max(14, round(scale * 20)), thickness)
        label = "{} ({:.1f}, {:.1f}){}".format(
            detection.color, detection.center_x, detection.center_y,
            " [possibly truncated]" if detection.possibly_truncated else "")
        x, y, _, _ = detection.bbox
        size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        tx = max(0, min(x, width - size[0] - 1))
        ty = min(height - baseline - 1, max(size[1] + 5, y - 8))
        cv2.putText(output, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.putText(output, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness, cv2.LINE_AA)
    note = "COLOR REGION CENTROID | {} candidates | {:.2f} ms".format(
        len(result.detections), result.elapsed_ms)
    cv2.putText(output, note, (10, max(22, round(scale * 28))),
                cv2.FONT_HERSHEY_SIMPLEX, scale * 0.8, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(output, note, (10, max(22, round(scale * 28))),
                cv2.FONT_HERSHEY_SIMPLEX, scale * 0.8, (255, 255, 255), thickness, cv2.LINE_AA)
    return output
