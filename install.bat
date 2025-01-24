@echo off
echo Creating Conda environment...
call conda env create -f environment.yml

echo Activating environment...
call conda activate gmap

echo Installing additional dependencies...
pip install -e .

echo Setup complete! You can now start JupyterLab by running:
echo jupyter lab