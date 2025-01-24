# CMIP6 Analysis Tool

## Overview
A Python-based tool for analyzing and visualizing CMIP6 (Coupled Model Intercomparison Project Phase 6) climate data using Google Earth Engine (GEE) and other geospatial libraries.

## Features
- Load and process CMIP6 climate datasets
- Calculate various climate indices
- Perform temporal and spatial analysis
- Generate interactive visualizations
- Handle complex geometric operations
- Time series analysis and period handling

## Core Components
- **`climate_analysis_tool.py`**: Core analysis functions for climate data
- **`cmip6_dataset.py`**: CMIP6 dataset loading and processing
- **`cmip6_indices.py`**: Implementation of climate indices calculations
- **`cmip6_visualizer.py`**: Visualization functions and plotting tools
- **`geometry_handler.py`**: Geometric operations and spatial analysis
- **`time_period_handler.py`**: Time series management and period analysis
- **`main.ipynb`**: Jupyter notebook demonstrating the complete workflow

## Prerequisites
- Python 3.11.10
- Anaconda or Miniconda
- Google Earth Engine account (for GEE functionality)

## Installation
```bash
# Clone the repository
git clone https://github.com/Saurav-JSUMS/CMIP6-Analysis-Tool.git
cd CMIP6-Analysis-Tool

# Create and activate the conda environment
conda env create -f environment.yml
conda activate gmap

# Install the package
pip install -e .
```

## Usage
```bash
# Activate environment
conda activate gmap

# Launch Jupyter Lab
jupyter lab

# Open `main.ipynb` to run analyses
```

## Dependencies
Key packages:
- `geemap`
- `geopandas`
- `numpy`
- `pandas`
- `ipykernel`
- `jupyterlab`
- `earthengine-api`
- `matplotlib`
- `seaborn`

## Troubleshooting

### GEE Authentication
- Ensure you're logged into your Google Earth Engine account
- Run `earthengine authenticate` if needed

### Environment Issues
- Make sure all dependencies are properly installed
- Check Python version compatibility (3.11.10)
- Try recreating the environment if issues persist

## Contact
- **Author**: Saurav Bhattarai
- **Institution**: Jackson State University
- **Email**: saurav.bhattarai.1999@gmail.com
