# Copyright 2022 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
r"""Beam pipeline that generates Middlebury `Other Datasets` triplet TFRecords.

Middlebury interpolation evaluation dataset consists of two subsets.

(1) Two frames only, without the intermediate golden frame. A total of 12 such
  pairs, with folder names (Army, Backyard, Basketball, Dumptruck,
  Evergreen, Grove, Mequon, Schefflera, Teddy, Urban, Wooden, Yosemite)

(2) Two frames together with the intermediate golden frame. A total of 12 such
  triplets, with folder names (Beanbags, Dimetrodon, DogDance, Grove2,
  Grove3, Hydrangea, MiniCooper, RubberWhale, Urban2, Urban3, Venus, Walking)

This script runs on (2), i.e. the dataset with the golden frames. For more
information, visit https://vision.middlebury.edu/flow/data.

Input to the script is the root-folder that contains the unzipped folders
of input pairs (other-data) and golen frames (other-gt-interp).

Output TFRecord is a tf.train.Example proto of each image triplet.
The feature_map takes the form:
  feature_map {
      'frame_0/encoded':
          tf.io.FixedLenFeature((), tf.string, default_value=''),
      'frame_0/format':
          tf.io.FixedLenFeature((), tf.string, default_value='jpg'),
      'frame_0/height':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'frame_0/width':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'frame_1/encoded':
          tf.io.FixedLenFeature((), tf.string, default_value=''),
      'frame_1/format':
          tf.io.FixedLenFeature((), tf.string, default_value='jpg'),
      'frame_1/height':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'frame_1/width':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'frame_2/encoded':
          tf.io.FixedLenFeature((), tf.string, default_value=''),
      'frame_2/format':
          tf.io.FixedLenFeature((), tf.string, default_value='jpg'),
      'frame_2/height':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'frame_2/width':
          tf.io.FixedLenFeature((), tf.int64, default_value=0),
      'path':
          tf.io.FixedLenFeature((), tf.string, default_value=''),
  }

Usage example:
  python3 -m frame_interpolation.datasets.create_middlebury_tfrecord \
    --input_dir=<root folder of middlebury-other> \
    --output_tfrecord_filepath=<output tfrecord filepath>
"""

import os

from . import util
from absl import app
from absl import flags
from absl import logging
import apache_beam as beam
import tensorflow as tf

_INPUT_DIR = flags.DEFINE_string(
    'input_dir',
    default='/root/path/to/middlebury-other',
    help='Path to the root directory of the frames.')

_OUTPUT_TFRECORD_FILEPATH = flags.DEFINE_string(
    'output_tfrecord_filepath',
    default=None,
    required=True,
    help='Filepath to the output TFRecord file.')

_NUM_SHARDS = flags.DEFINE_integer('num_shards',
    default=3,
    help='Number of shards used for the output.')

# Image key -> offset for frame interpolator: start / middle / end frame offset.
_INTERPOLATOR_IMAGES_MAP = {
    'frame_0': -1,
    'frame_1': 0,
    'frame_2': 1,
}


def main(unused_argv):
  """Creates and runs a Beam pipeline to write frame triplets as a TFRecord."""

  frames_list = sorted(tf.io.gfile.listdir(_INPUT_DIR.value))
  print(len(frames_list))

  triplet_dicts = []
  for index in range(1, len(frames_list) - 1, 2):
    triplet_dict = {
        image_key: os.path.join(_INPUT_DIR.value, frames_list[index + image_offset])
        for image_key, image_offset in _INTERPOLATOR_IMAGES_MAP.items()
    }
    triplet_dicts.append(triplet_dict)

  p = beam.Pipeline('DirectRunner')
  (p | 'ReadInputTripletDicts' >> beam.Create(triplet_dicts)  # pylint: disable=expression-not-assigned
   | 'GenerateSingleExample' >> beam.ParDo(
       util.ExampleGenerator(_INTERPOLATOR_IMAGES_MAP))
   | 'WriteToTFRecord' >> beam.io.tfrecordio.WriteToTFRecord(
       file_path_prefix=_OUTPUT_TFRECORD_FILEPATH.value,
       num_shards=_NUM_SHARDS.value,
       coder=beam.coders.BytesCoder()))
  result = p.run()
  result.wait_until_finish()

  logging.info('Succeeded in creating the output TFRecord file: \'%s@%s\'.',
    _OUTPUT_TFRECORD_FILEPATH.value, str(_NUM_SHARDS.value))

if __name__ == '__main__':
  app.run(main)
