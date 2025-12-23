import cv2
import numpy as np
import os
import glob
import argparse
import sys
import json

# Ensure stdout uses utf-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def log(msg, type="info"):
    # Print JSON object for frontend to parse
    print(json.dumps({"type": type, "msg": msg}), flush=True)

def cv_imread(file_path):
    try:
        stream = np.fromfile(file_path, dtype=np.uint8)
        cv_img = cv2.imdecode(stream, cv2.IMREAD_UNCHANGED)
        return cv_img
    except Exception as e:
        return None

def cv_imwrite(file_path, img):
    try:
        ext = os.path.splitext(file_path)[1]
        if not ext:
            ext = ".png"
        result, data = cv2.imencode(ext, img)
        if result:
            data.tofile(file_path)
            return True
        return False
    except Exception:
        return False

def process_dual_outputs(original_path, template_path, output_res_path, output_fixed_path, target_w, target_h):
    img_orig = cv_imread(original_path)
    img_temp = cv_imread(template_path)

    if img_orig is None:
        log(f"Failed to read original: {original_path}", "error")
        return False
    if img_temp is None:
        log(f"Failed to read template: {template_path}", "error")
        return False

    def to_gray(img):
        if len(img.shape) == 3:
            if img.shape[2] == 4:
                return cv2.cvtColor(img[:,:,:3], cv2.COLOR_BGR2GRAY)
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    gray_orig = to_gray(img_orig)
    gray_temp = to_gray(img_temp)

    # Use SIFT
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(gray_temp, None)
    kp2, des2 = sift.detectAndCompute(gray_orig, None)

    if des1 is None or des2 is None:
        return False

    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des1, des2, k=2)
    
    good = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good.append(m)

    if len(good) < 10:
        return False

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

    if M is None:
        return False

    h_temp, w_temp = gray_temp.shape[:2]
    pts = np.float32([[0, 0], [0, h_temp], [w_temp, h_temp], [w_temp, 0]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(pts, M)

    xmin, ymin = np.int32(dst.min(axis=0).ravel())
    xmax, ymax = np.int32(dst.max(axis=0).ravel())
    
    center_x, center_y = (xmin + xmax) / 2, (ymin + ymax) / 2
    orig_h, orig_w = img_orig.shape[:2]

    # Target calculation
    ratio = target_w / target_h
    final_h = ymax - ymin
    final_w = final_h * ratio

    x1 = int(center_x - final_w / 2)
    y1 = int(center_y - final_h / 2)
    x2, y2 = int(x1 + final_w), int(y1 + final_h)

    # Boundary checks
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(orig_w, x2), min(orig_h, y2)

    high_res_crop = img_orig[y1:y2, x1:x2]

    if high_res_crop.size == 0:
        return False

    if output_res_path:
        cv_imwrite(output_res_path, high_res_crop)

    if output_fixed_path:
        fixed_res_img = cv2.resize(high_res_crop, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        cv_imwrite(output_fixed_path, fixed_res_img)

    return True

def main():
    parser = argparse.ArgumentParser(description="Smart Crop Tool")
    parser.add_argument("--templates", required=True, help="Path to templates directory")
    parser.add_argument("--input", required=True, help="Path to input images directory")
    parser.add_argument("--output-high", help="Path to output high-res crops")
    parser.add_argument("--output-fixed", help="Path to output fixed-size resized crops")
    parser.add_argument("--width", type=int, default=456, help="Target width")
    parser.add_argument("--height", type=int, default=564, help="Target height")

    args = parser.parse_args()

    # Create directories
    if args.output_high and not os.path.exists(args.output_high):
        os.makedirs(args.output_high)
    if args.output_fixed and not os.path.exists(args.output_fixed):
        os.makedirs(args.output_fixed)

    # Get files
    temp_files = glob.glob(os.path.join(args.templates, "*"))
    orig_files = glob.glob(os.path.join(args.input, "*"))
    
    # Filter for images
    valid_exts = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
    temp_files = [f for f in temp_files if os.path.splitext(f)[1].lower() in valid_exts]
    orig_files = [f for f in orig_files if os.path.splitext(f)[1].lower() in valid_exts]

    log(f"Found {len(temp_files)} templates and {len(orig_files)} input images")

    processed_count = 0
    
    for t_path in temp_files:
        name = os.path.splitext(os.path.basename(t_path))[0]
        # Matching logic: template name inside original name
        matching_orig = [o for o in orig_files if name in os.path.basename(o)]

        if not matching_orig:
            # log(f"No match for template: {name}", "info")
            continue

        o_path = matching_orig[0]
        
        out_res = None
        if args.output_high:
            out_res = os.path.join(args.output_high, f"{name}.png")
            
        out_fixed = None
        if args.output_fixed:
            out_fixed = os.path.join(args.output_fixed, f"{name}.png")

        try:
            success = process_dual_outputs(o_path, t_path, out_res, out_fixed, args.width, args.height)
            if success:
                log(f"Processed: {name}", "success")
                processed_count += 1
            else:
                log(f"Failed to match/crop: {name}", "error")
        except Exception as e:
            log(f"Error processing {name}: {str(e)}", "error")

    log(f"Complete. Processed {processed_count} images.", "success")

if __name__ == "__main__":
    main()
