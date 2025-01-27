"""
cmip6_indices.py
Calculates standard climate indices for CMIP6 data using Earth Engine
"""

from typing import Dict, Tuple, Optional, List
from enum import Enum
import ee
from dataclasses import dataclass

class IndexCategory(Enum):
    """Categories of climate indices"""
    PRECIPITATION = "precipitation"
    TEMPERATURE = "temperature"

@dataclass
class IndexInfo:
    """Information about a climate index"""
    name: str
    category: IndexCategory
    description: str
    units: str
    requires_daily: bool = True
    min_value: float = 0
    max_value: float = 100
    palette: List[str] = None

    def __post_init__(self):
        if self.palette is None:
            self.palette = ['#deebf7', '#9ecae1', '#3182bd'] if self.category == IndexCategory.PRECIPITATION else \
                          ['#2166ac', '#f7f7f7', '#b2182b']

class CMIP6Indices:
    """
    Calculates standardized climate indices from CMIP6 data
    """
    
    # Define available indices following WMO guidelines
    INDICES = {
        # Precipitation indices
        'annual_total_precip': IndexInfo(
            name='Annual Total Precipitation',
            category=IndexCategory.PRECIPITATION,
            description='Total precipitation over the year',
            units='mm/year',
            min_value=0,
            max_value=3000
        ),
        'rx1day': IndexInfo(
            name='Maximum 1-day Precipitation',
            category=IndexCategory.PRECIPITATION,
            description='Annual maximum 1-day precipitation',
            units='mm/day',
            min_value=0,
            max_value=200
        ),
        'rx5day': IndexInfo(
            name='Maximum 5-day Precipitation',
            category=IndexCategory.PRECIPITATION,
            description='Annual maximum 5-day precipitation',
            units='mm/5day',
            min_value=0,
            max_value=400
        ),
        'sdii': IndexInfo(
            name='Simple Daily Intensity Index',
            category=IndexCategory.PRECIPITATION,
            description='Mean precipitation on wet days (≥1mm)',
            units='mm/day',
            min_value=0,
            max_value=50
        ),
        'r10mm': IndexInfo(
            name='Heavy Precipitation Days',
            category=IndexCategory.PRECIPITATION,
            description='Annual count of days with precipitation ≥10mm',
            units='days',
            min_value=0,
            max_value=365
        ),
        'r20mm': IndexInfo(
            name='Very Heavy Precipitation Days',
            category=IndexCategory.PRECIPITATION,
            description='Annual count of days with precipitation ≥20mm',
            units='days',
            min_value=0,
            max_value=365
        ),
        'cdd': IndexInfo(
            name='Consecutive Dry Days',
            category=IndexCategory.PRECIPITATION,
            description='Maximum number of consecutive days with precipitation <1mm',
            units='days',
            min_value=0,
            max_value=365
        ),
        'cwd': IndexInfo(
            name='Consecutive Wet Days',
            category=IndexCategory.PRECIPITATION,
            description='Maximum number of consecutive days with precipitation ≥1mm',
            units='days',
            min_value=0,
            max_value=365
        ),
        
        # Temperature indices
        'txx': IndexInfo(
            name='Maximum Temperature',
            category=IndexCategory.TEMPERATURE,
            description='Annual maximum value of daily maximum temperature',
            units='°C',
            min_value=-10,
            max_value=45
        ),
        'tnn': IndexInfo(
            name='Minimum Temperature',
            category=IndexCategory.TEMPERATURE,
            description='Annual minimum value of daily minimum temperature',
            units='°C',
            min_value=-30,
            max_value=25
        ),
        'dtr': IndexInfo(
            name='Diurnal Temperature Range',
            category=IndexCategory.TEMPERATURE,
            description='Mean difference between daily max and min temperature',
            units='°C',
            min_value=0,
            max_value=20
        ),
        'fd': IndexInfo(
            name='Frost Days',
            category=IndexCategory.TEMPERATURE,
            description='Annual count of days with minimum temperature <0°C',
            units='days',
            min_value=0,
            max_value=365
        ),
        'su': IndexInfo(
            name='Summer Days',
            category=IndexCategory.TEMPERATURE,
            description='Annual count of days with maximum temperature >25°C',
            units='days',
            min_value=0,
            max_value=365
        ),
        'tr': IndexInfo(
            name='Tropical Nights',
            category=IndexCategory.TEMPERATURE,
            description='Annual count of days with minimum temperature >20°C',
            units='days',
            min_value=0,
            max_value=365
        ),
        'wsdi': IndexInfo(
            name='Warm Spell Duration',
            category=IndexCategory.TEMPERATURE,
            description='Annual count of days with at least 6 consecutive days when max temperature >90th percentile',
            units='days',
            min_value=0,
            max_value=365
        ),
        'csdi': IndexInfo(
            name='Cold Spell Duration',
            category=IndexCategory.TEMPERATURE,
            description='Annual count of days with at least 6 consecutive days when min temperature <10th percentile',
            units='days',
            min_value=0,
            max_value=365
        ),

        # Additional precipitation indices
        'r90p': IndexInfo(
            name='Very Wet Days',
            category=IndexCategory.PRECIPITATION,
            description='Annual count of days when precipitation > 90th percentile',
            units='days',
            min_value=0,
            max_value=365
        ),
        'r95p': IndexInfo(
            name='Extremely Wet Days',
            category=IndexCategory.PRECIPITATION, 
            description='Annual count of days when precipitation > 95th percentile',
            units='days',
            min_value=0,
            max_value=365
        ),
        'r99p': IndexInfo(
            name='Exceptionally Wet Days',
            category=IndexCategory.PRECIPITATION,
            description='Annual count of days when precipitation > 99th percentile',
            units='days',
            min_value=0,
            max_value=365
        ),
        'prcptot': IndexInfo(
            name='Annual Total Wet-day Precipitation',
            category=IndexCategory.PRECIPITATION,
            description='Annual total precipitation from days ≥ 1mm',
            units='mm',
            min_value=0,
            max_value=3000
        ),

        # Additional temperature indices
        'tn10p': IndexInfo(
            name='Cool Nights',
            category=IndexCategory.TEMPERATURE,
            description='Percentage of days when TN < 10th percentile',
            units='%',
            min_value=0,
            max_value=100
        ),
        'tx90p': IndexInfo(
            name='Warm Days',
            category=IndexCategory.TEMPERATURE,
            description='Percentage of days when TX > 90th percentile',
            units='%',
            min_value=0,
            max_value=100
        ),
        'gsl': IndexInfo(
            name='Growing Season Length',
            category=IndexCategory.TEMPERATURE,
            description='Annual count between first span of 6 days with T>5°C and first span of 6 days with T<5°C',
            units='days',
            min_value=0,
            max_value=365
        ),
    }

    @classmethod
    def list_indices(cls, category: Optional[IndexCategory] = None) -> List[str]:
        """List available indices, optionally filtered by category"""
        if category:
            return [name for name, info in cls.INDICES.items() 
                   if info.category == category]
        return list(cls.INDICES.keys())

    @classmethod
    def get_index_info(cls, index_name: str) -> IndexInfo:
        """Get information about a specific index"""
        if index_name not in cls.INDICES:
            raise ValueError(f"Unknown index: {index_name}")
        return cls.INDICES[index_name]

    @staticmethod
    def _calculate_consecutive_days(collection: ee.ImageCollection, 
                                 condition_func, max_only: bool = True) -> ee.Image:
        """Helper to calculate consecutive days meeting a condition"""
        def increment_streak(current, previous):
            previous_streak = ee.Image(ee.List(previous).get(-1))
            current_image = ee.Image(current)
            streak = condition_func(current_image)\
                .multiply(previous_streak.add(1))\
                .rename('streak')
            return ee.List(previous).add(streak)

        # Initialize with zero image
        initial = ee.List([ee.Image.constant(0).rename('streak')])
        
        # Calculate streaks
        streaks = ee.List(collection.iterate(increment_streak, initial))
        
        # Convert to collection and get maximum if requested
        result = ee.ImageCollection(streaks.slice(1))
        if max_only:
            return result.max()
        return result

    def calculate_index(self, collection: ee.ImageCollection, index_name: str,
                       precip_threshold: float = 1.0) -> Tuple[ee.Image, IndexInfo]:
        """
        Calculate a specific climate index
        
        Args:
            collection: Earth Engine ImageCollection with daily data
            index_name: Name of index to calculate
            precip_threshold: Threshold for wet days (mm/day)
            
        Returns:
            Tuple of (calculated index image, index information)
        """
        info = self.get_index_info(index_name)
        
        try:
            if index_name == 'annual_total_precip':
                result = collection.select(['precipitation']).sum()
            
            elif index_name == 'rx1day':
                result = collection.select(['precipitation']).max()
            
            elif index_name == 'rx5day':
                # Calculate 5-day rolling sum
                collection_list = collection.toList(collection.size())
                size = collection.size().subtract(4)
                
                def calculate_5day_sum(i):
                    i = ee.Number(i)
                    images = collection_list.slice(i, i.add(5))
                    image_collection = ee.ImageCollection.fromImages(images)
                    return image_collection.select(['precipitation']).sum()

                five_day_sums = ee.ImageCollection.fromImages(
                    ee.List.sequence(0, size.subtract(1)).map(calculate_5day_sum)
                )
                result = five_day_sums.max()
            
            elif index_name == 'sdii':
                # Count wet days
                wet_days = collection.select(['precipitation'])\
                    .map(lambda img: img.gte(precip_threshold))
                wet_day_count = wet_days.sum()
                
                # Calculate mean precipitation on wet days
                total_precip = collection.select(['precipitation']).sum()
                result = total_precip.divide(wet_day_count)
            
            elif index_name in ['r10mm', 'r20mm']:
                threshold = 10 if index_name == 'r10mm' else 20
                result = collection.select(['precipitation'])\
                    .map(lambda img: img.gte(threshold))\
                    .sum()
            
            elif index_name == 'cdd':
                result = self._calculate_consecutive_days(
                    collection,
                    lambda img: img.select(['precipitation']).lt(precip_threshold)
                )
            
            elif index_name == 'cwd':
                result = self._calculate_consecutive_days(
                    collection,
                    lambda img: img.select(['precipitation']).gte(precip_threshold)
                )
            
            elif index_name == 'txx':
                result = collection.select(['tasmax']).max()
            
            elif index_name == 'tnn':
                result = collection.select(['tasmin']).min()
            
            elif index_name == 'dtr':
                result = collection.map(
                    lambda img: img.select(['tasmax'])\
                        .subtract(img.select(['tasmin']))
                ).mean()
            
            elif index_name == 'fd':
                result = collection.select(['tasmin'])\
                    .map(lambda img: img.lt(273.15))\
                    .sum()
            
            elif index_name == 'su':
                result = collection.select(['tasmax'])\
                    .map(lambda img: img.gt(273.15 + 25))\
                    .sum()
            
            elif index_name == 'tr':
                result = collection.select(['tasmin'])\
                    .map(lambda img: img.gt(273.15 + 20))\
                    .sum()
            
            elif index_name in ['wsdi', 'csdi']:
                # Calculate percentile threshold
                if index_name == 'wsdi':
                    percentile = collection.select(['tasmax'])\
                        .reduce(ee.Reducer.percentile([90]))
                    collection = collection.select(['tasmax'])
                    condition = lambda img: img.gt(percentile)
                else:
                    percentile = collection.select(['tasmin'])\
                        .reduce(ee.Reducer.percentile([10]))
                    collection = collection.select(['tasmin'])
                    condition = lambda img: img.lt(percentile)
                
                # Calculate spell duration
                result = self._calculate_consecutive_days(
                    collection, condition
                )
            
            # New index calculations
            elif index_name == 'r90p':
                # Calculate 90th percentile precipitation threshold
                threshold = collection.select(['precipitation'])\
                    .reduce(ee.Reducer.percentile([90]))
                # Count days above threshold
                result = collection.select(['precipitation'])\
                    .map(lambda img: img.gt(threshold))\
                    .sum()

            elif index_name == 'r95p':
                # Calculate 95th percentile precipitation threshold
                threshold = collection.select(['precipitation'])\
                    .reduce(ee.Reducer.percentile([95]))
                # Count days above threshold  
                result = collection.select(['precipitation'])\
                    .map(lambda img: img.gt(threshold))\
                    .sum()

            elif index_name == 'r99p':
                # Calculate 99th percentile precipitation threshold
                threshold = collection.select(['precipitation'])\
                    .reduce(ee.Reducer.percentile([99]))
                # Count days above threshold
                result = collection.select(['precipitation'])\
                    .map(lambda img: img.gt(threshold))\
                    .sum()

            elif index_name == 'prcptot':
                # Calculate total precipitation from wet days
                result = collection.select(['precipitation'])\
                    .map(lambda img: img.updateMask(img.gte(precip_threshold)))\
                    .sum()

            elif index_name == 'tn10p':
                # Calculate 10th percentile of minimum temperature
                threshold = collection.select(['tasmin'])\
                    .reduce(ee.Reducer.percentile([10]))
                # Count days below threshold
                result = collection.select(['tasmin'])\
                    .map(lambda img: img.lt(threshold))\
                    .sum()

            elif index_name == 'tx90p':
                # Calculate 90th percentile of maximum temperature
                threshold = collection.select(['tasmax'])\
                    .reduce(ee.Reducer.percentile([90]))
                # Count days above threshold
                result = collection.select(['tasmax'])\
                    .map(lambda img: img.gt(threshold))\
                    .sum()

            elif index_name == 'gsl':
                # Growing Season Length
                # Start: First span of 6 days with daily mean temperature > 5°C
                # End: First span of 6 days with daily mean temperature < 5°C
                temp_threshold = 5 + 273.15  # Convert to Kelvin
                
                def calc_daily_mean(img):
                    return img.select(['tasmax']).add(img.select(['tasmin'])).divide(2)
                
                daily_mean = collection.map(calc_daily_mean)
                warm_days = daily_mean.map(lambda img: img.gt(temp_threshold))
                
                # Find start and end of growing season
                result = self._calculate_consecutive_days(warm_days, 
                    lambda img: img.gt(0), max_only=True)

            else:
                raise ValueError(f"Index calculation not implemented: {index_name}")
            
            return result.rename(index_name), info
            
        except Exception as e:
            raise ValueError(f"Error calculating {index_name}: {str(e)}")

    def get_visualization_params(self, index_name: str) -> Dict:
        """Get visualization parameters for an index"""
        info = self.get_index_info(index_name)
        return {
            'min': info.min_value,
            'max': info.max_value,
            'palette': info.palette,
            'opacity': 0.8
        }