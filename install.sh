#!/bin/bash
echo "Creating Conda environment..."
conda env create -f environment.yml

echo "Activating environment..."
conda activate gmap

echo "Installing additional dependencies..."
pip install -e .

echo "Setup complete! You can now start JupyterLab by running:"
echo "jupyter lab"