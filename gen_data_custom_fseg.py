
# Copyright 2018 The TensorFlow Authors All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

""" Offline data generation for the KITTI dataset."""

import os
from absl import app
from absl import flags
from absl import logging
import numpy as np
import cv2
import os, glob

import alignment
from alignment import compute_overlap
from alignment import align
import tensorflow as tf

SEQ_LENGTH = 5
WIDTH = 416
HEIGHT = 128
STEPSIZE = 1
INPUT_DIR = 'C:/Users/bella/Documents/Bachelor/kitti'
OUTPUT_DIR = 'C:/Users/bella/Documents/Bachelor/kitti'


def get_line(file, start):
    file = open(file, 'r')
    lines = file.readlines()
    lines = [line.rstrip() for line in lines]
    ret = None
    for line in lines:
        nline = line.split(': ')
        if nline[0]==start:
            ret = nline[1].split(' ')
            ret = np.array([float(r) for r in ret], dtype=float)
            ret = ret.reshape((3,4))[0:3, 0:3]
            break
    file.close()
    return ret


def crop(img, segimg, fx, fy, cx, cy):
    # Perform center cropping, preserving 50% vertically.
    middle_perc = 0.50
    left = 1-middle_perc
    half = left/2
    a = img[int(img.shape[0]*(half)):int(img.shape[0]*(1-half)), :]
    aseg = segimg[int(segimg.shape[0]*(half)):int(segimg.shape[0]*(1-half)), :]
    cy /= (1/middle_perc)

    # Resize to match target height while preserving aspect ratio.
    wdt = int((128*a.shape[1]/a.shape[0]))
    x_scaling = float(wdt)/a.shape[1]
    y_scaling = 128.0/a.shape[0]
    b = cv2.resize(a, (wdt, 128))
    bseg = cv2.resize(aseg, (wdt, 128))

    # Adjust intrinsics.
    fx*=x_scaling
    fy*=y_scaling
    cx*=x_scaling
    cy*=y_scaling

    # Perform center cropping horizontally.
    remain = b.shape[1] - 416
    cx /= (b.shape[1]/416)
    c = b[:, int(remain/2):b.shape[1]-int(remain/2)]
    cseg = bseg[:, int(remain/2):b.shape[1]-int(remain/2)]

    return c, cseg, fx, fy, cx, cy


def run_all():
  ct = 0
if not OUTPUT_DIR.endswith('/'):
    OUTPUT_DIR = OUTPUT_DIR + '/'

for d in glob.glob(INPUT_DIR + '/*/'):
    date = d.split('\\')[-2]
    file_calibration = d + 'calib_cam_to_cam.txt'
    calib_raw = [get_line(file_calibration, 'P_rect_02'), get_line(file_calibration, 'P_rect_03')]

    for d2 in glob.glob(d + '*/'):
        seqname = d2.split('\\')[-2]
        number = int(seqname.split("_")[-2])
        if int(number)<3 :
            print('Processing sequence', seqname)
            for subfolder in ['image_02/data', 'image_03/data']:
                output_filepath = os.path.join(OUTPUT_DIR, 'train.txt')
                written_before = []
                gfile = tf.gfile
                file_mode = 'a'
                ct = 1
                seqname = d2.split('\\')[-2] + subfolder.replace('image', '').replace('/data', '')
                if not os.path.exists(OUTPUT_DIR + seqname):
                    os.makedirs(OUTPUT_DIR + seqname)

                calib_camera = calib_raw[0] if subfolder=='mask' else calib_raw[1]
                folder = d2 + subfolder
                files = glob.glob(folder + '/*.png')
                segs = [file for file in files if 'fseg' in file]
                segs = sorted(segs,key=lambda x: int(x.split('_')[-2]))
                # files = [file for file in files if not 'disp' in file and not 'flip' in file and not 'seg' in file]
                # files = sorted(files)
                #print('filesss = ', files)
                for i in range(SEQ_LENGTH, len(segs)+1, STEPSIZE):
                    imgnum = str(ct).zfill(10)
                    # if os.path.exists(OUTPUT_DIR + seqname + '/' + imgnum + '-fseg.png'):
                    #     ct+=1
                    #     continue
                    big_img = np.zeros(shape=(HEIGHT, WIDTH*SEQ_LENGTH, 3))
                    wct = 0
                    wrt = 0

                    for j in range(i-SEQ_LENGTH, i):  # Collect frames for this sample.
                        if wrt == 0:
                            img0 = cv2.imread(segs[j])
                        elif wrt == 1:
                            img1 = cv2.imread(segs[j])
                        elif wrt == 2:
                            img2 = cv2.imread(segs[j])
                        elif wrt == 3:
                            img3 = cv2.imread(segs[j])
                        elif wrt == 4:
                            img4 = cv2.imread(segs[j])

                        wrt+=1


                        print('Nama segs = ', segs[j])
                        ORIGINAL_HEIGHT, ORIGINAL_WIDTH, _ = img0.shape

                        zoom_x = WIDTH/ORIGINAL_WIDTH
                        zoom_y = HEIGHT/ORIGINAL_HEIGHT

                        # Adjust intrinsics.
                        calib_current = calib_camera.copy()
                        calib_current[0, 0] *= zoom_x
                        calib_current[0, 2] *= zoom_x
                        calib_current[1, 1] *= zoom_y
                        calib_current[1, 2] *= zoom_y

                        calib_representation = ','.join([str(c) for c in calib_current.flatten()])

                        if wrt == 5:
                            img0, img1, img2,img3,img4 = align(img0, img1, img2,img3,img4, threshold_same=0.5)
                            img0 = cv2.resize(img0, (WIDTH, HEIGHT))
                            img1 = cv2.resize(img1, (WIDTH, HEIGHT))
                            img2 = cv2.resize(img2, (WIDTH, HEIGHT))
                            img3 = cv2.resize(img3, (WIDTH, HEIGHT))
                            img4 = cv2.resize(img4, (WIDTH, HEIGHT))

                            big_img[:,0*WIDTH:(0+1)*WIDTH] = img0
                            big_img[:,1*WIDTH:(1+1)*WIDTH] = img1
                            big_img[:,2*WIDTH:(2+1)*WIDTH] = img2
                            big_img[:,3*WIDTH:(3+1)*WIDTH] = img3
                            big_img[:,4*WIDTH:(4+1)*WIDTH] = img4

                    #imgnum = imgnum[6:]
                    print("big_img = ", big_img.shape)
                    # big_imgg = cv2.cvtColor(big_img, cv2.COLOR_BGR2GRAY)

                    # Tes aing
                    print("1 = ", OUTPUT_DIR)
                    print("2 = ", seqname)
                    print("3 = ", imgnum)
                    print("output = ", OUTPUT_DIR + seqname + '/' + imgnum + '-fseg.png')

                    #modify train txt file 
                    with gfile.Open(output_filepath, file_mode) as current_output_handle:
                        current_output_handle.write(seqname+" "+str(imgnum)+"\n")
                    written_before.append(output_filepath)
                    big_img = cv2.cvtColor(big_img.astype(np.uint8), cv2.COLOR_BGR2GRAY)
                    cv2.imwrite(OUTPUT_DIR + seqname + '/' + imgnum + '-fseg.png', big_img)
                    simpan = cv2.imread(OUTPUT_DIR + seqname + '/' + imgnum + '-fseg.png', 0)
                    print("simpan = ", simpan.shape)
                    cv2.imwrite(OUTPUT_DIR + seqname + '/' + imgnum + '-fseg.png', simpan)
                    #f = open(OUTPUT_DIR + seqname + '/' + imgnum + '_cam.txt', 'w')
                    #f.write(calib_representation)
                    #f.close()
                    ct+=1

def main(_):
    run_all()


if __name__ == '__main__':
    app.run(main)
