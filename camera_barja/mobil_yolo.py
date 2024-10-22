# Install tensorflow-directml
pip install tensorflow-directml-plugin

import tensorflow as tf
print("GPU Available:", tf.config.list_physical_devices('GPU'))