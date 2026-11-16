#!/usr/bin/env python
import traceback
from os import path, environ
from urllib.parse import urlparse

import cv2
import flask
import numpy as np
import requests
from flask import request, jsonify

from auth import token_required
from lib.detection_model import load_net, detect

THRESH = 0.08  # The threshold for a box to be considered a positive detection
SESSION_TTL_SECONDS = 60 * 2
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # Refuse to download anything larger than this

app = flask.Flask(__name__)

status = dict()

# SECURITY WARNING: don't run with debug turned on in production!
app.config['DEBUG'] = environ.get('DEBUG') == 'True'

model_dir = path.join(path.dirname(path.realpath(__file__)), 'model')
net_main = load_net(path.join(model_dir, 'model.cfg'), path.join(model_dir, 'model.meta'))


def fetch_image(url):
    """Download the image at url, limited to http(s) and MAX_IMAGE_BYTES."""
    if urlparse(url).scheme not in ('http', 'https'):
        raise ValueError('Only http and https image URLs are supported')

    data = bytearray()
    with requests.get(url, stream=True, timeout=(0.1, 5)) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError('Image is larger than {} bytes'.format(MAX_IMAGE_BYTES))
    return data


@app.route('/p/', methods=['GET'])
@token_required
def get_p():
    if 'img' in request.args:
        try:
            img_array = np.array(fetch_image(request.args['img']), dtype=np.uint8)
            img = cv2.imdecode(img_array, -1)
            detections = detect(net_main, img, thresh=THRESH)
            return jsonify({'detections': detections})
        except:
            traceback.print_exc()
    else:
        app.logger.warning("Invalid request params: {}".format(request.args))

    return jsonify({'detections': []})


@app.route('/hc/', methods=['GET'])
def health_check():
    return 'ok' if net_main is not None else 'error'


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3333, threaded=False)
