"""
cmip6_dataset.py
Enhanced version of CMIP6Dataset with improved model switching and data handling
"""

from typing import Dict, Any, Optional, List, Tuple, Set
import ee
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from src.cmip6_indices import CMIP6Indices, IndexCategory, IndexInfo

class ScenarioType(Enum):
    """Available SSP scenarios"""
    SSP245 = "ssp245"
    SSP585 = "ssp585"

class TimeFrameType(Enum):
    """Types of time frames for analysis"""
    HISTORICAL = "historical"
    NEAR_FUTURE = "near_future"
    FAR_FUTURE = "far_future"

@dataclass
class TimeFrameConfig:
    """Configuration for time frame periods"""
    min_year: int
    max_year: int
    min_duration: int = 20  # Minimum duration in years

    def validate_period(self, start_year: int, end_year: int) -> bool:
        """Validate if a period fits within constraints"""
        if not (self.min_year <= start_year <= self.max_year):
            return False
        if not (self.min_year <= end_year <= self.max_year):
            return False
        if end_year - start_year + 1 < self.min_duration:
            return False
        return True

@dataclass
class CacheKey:
    """Key for caching computed results"""
    model: str
    scenario: str
    timeframe: TimeFrameType
    start_date: str
    end_date: str
    variable: str
    geometry_hash: str

class CMIP6Dataset:
    """
    Enhanced CMIP6Dataset with support for efficient model switching
    """
    
    # Time frame configurations
    TIME_FRAMES = {
        TimeFrameType.HISTORICAL: TimeFrameConfig(1980, 2014),
        TimeFrameType.NEAR_FUTURE: TimeFrameConfig(2015, 2060),
        TimeFrameType.FAR_FUTURE: TimeFrameConfig(2061, 2100)
    }

    def __init__(self, model_name: str, scenario: ScenarioType):
        """Initialize dataset with specified model and scenario"""
        if model_name not in self.list_available_models():
            raise ValueError(f"Invalid model name: {model_name}")
        self.model = model_name
        self.model_name = model_name
        self.scenario = scenario
        self.base_collection_id = "NASA/GDDP-CMIP6"
        self.indices_calculator = CMIP6Indices()
        self._ee_collection = None
        self._cache: Dict[str, Any] = {}
        self._geometry_hashes: Set[str] = set()

    @staticmethod
    def list_available_models() -> List[str]:
        """Get list of available CMIP6 models"""
        return [
            'ACCESS-CM2', 'ACCESS-ESM1-5', 'BCC-CSM2-MR', 'CESM2',
            'CESM2-WACCM', 'CMCC-CM2-SR5', 'CMCC-ESM2', 'CNRM-CM6-1',
            'CNRM-ESM2-1', 'CanESM5', 'EC-Earth3', 'EC-Earth3-Veg-LR',
            'FGOALS-g3', 'GFDL-ESM4', 'GISS-E2-1-G', 'HadGEM3-GC31-LL',
            'HadGEM3-GC31-MM', 'INM-CM4-8', 'INM-CM5-0', 'IPSL-CM6A-LR',
            'KACE-1-0-G', 'KIOST-ESM', 'MIROC-ES2L', 'MIROC6',
            'MPI-ESM1-2-HR', 'MPI-ESM1-2-LR', 'MRI-ESM2-0', 'NorESM2-LM',
            'NorESM2-MM', 'TaiESM1', 'UKESM1-0-LL'
        ]

    def _get_cache_key(self, timeframe: TimeFrameType, start_date: str, 
                      end_date: str, geometry: ee.Geometry, variable: str) -> str:
        """Generate cache key for a specific request"""
        geometry_hash = str(hash(geometry.serialize()))
        self._geometry_hashes.add(geometry_hash)
        
        key = CacheKey(
            model=self.model_name,
            scenario=self.scenario.value,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            variable=variable,
            geometry_hash=geometry_hash
        )
        return str(hash(str(key)))

    def _clear_old_cache(self, max_entries: int = 100):
        """Clear old cache entries if cache size exceeds limit"""
        if len(self._cache) > max_entries:
            # Keep most recent entries
            sorted_keys = sorted(self._cache.keys(), 
                               key=lambda k: self._cache[k]['timestamp'])
            for key in sorted_keys[:-max_entries]:
                del self._cache[key]

    def process_collection(self, collection: ee.ImageCollection, 
                         variable: str) -> ee.ImageCollection:
        """Process collection to convert units"""
        var_info = self.get_variable_info(variable)
        
        if variable == 'precipitation':
            # Convert from kg/m^2/s to mm/day
            return collection.map(lambda img: img
                                .multiply(86400)  # seconds in day
                                .rename('precipitation'))
        elif variable in ['temperature', 'tasmax', 'tasmin']:
            # Convert from K to °C
            return collection.map(lambda img: img
                                .subtract(273.15)
                                .rename(variable))
        else:
            raise ValueError(f"Unknown variable: {variable}")
        
    def calculate_batch_indices(self, timeframe: TimeFrameType,
                           features: ee.FeatureCollection,
                           geometry: ee.Geometry,
                           index_name: str) -> ee.FeatureCollection:
        """Calculate indices for multiple time periods efficiently"""
        try:
            # Get index info and required variables
            index_info = CMIP6Indices.get_index_info(index_name)
            
            def calculate_for_feature(feature):
                start_date = ee.String(feature.get('start_date'))
                end_date = ee.String(feature.get('end_date'))
                
                # Get required collections based on index category
                if index_info.category == IndexCategory.PRECIPITATION:
                    collection = self.get_collection(
                        timeframe, start_date, end_date, geometry, 'precipitation'
                    )
                else:  # Temperature indices
                    tasmax = self.get_collection(
                        timeframe, start_date, end_date, geometry, 'tasmax'
                    )
                    tasmin = self.get_collection(
                        timeframe, start_date, end_date, geometry, 'tasmin'
                    )
                    collection = tasmax.combine(tasmin)
                
                # Calculate the index
                result, _ = self.indices_calculator.calculate_index(collection, index_name)
                return feature.set('result', result)
            
            return features.map(calculate_for_feature)
            
        except Exception as e:
            raise ValueError(f"Error calculating batch indices: {str(e)}")

    def get_collection(self, timeframe: TimeFrameType, 
                    start_date: str, end_date: str,
                    geometry: ee.Geometry,
                    variable: str) -> ee.ImageCollection:
        """Get Earth Engine ImageCollection with optimized caching"""
        cache_key = self._get_cache_key(timeframe, start_date, end_date, geometry, variable)
        
        if cache_key in self._cache:
            return self._cache[cache_key]['collection']
        
        try:
            # Get variable information and band name
            var_info = self.get_variable_info(variable)
            band_name = var_info['ee_name']
            
            # Create base collection with filters
            collection = ee.ImageCollection(self.base_collection_id)\
                .filter(ee.Filter.eq('model', self.model_name))\
                .filter(ee.Filter.date(start_date, end_date))\
                .filterBounds(geometry)\
                .select(band_name)
            
            # Add scenario filter
            if timeframe == TimeFrameType.HISTORICAL:
                collection = collection.filter(ee.Filter.eq('scenario', 'historical'))
            else:
                collection = collection.filter(ee.Filter.eq('scenario', self.scenario.value))
            
            # Process the collection (unit conversions)
            processed_collection = self.process_collection(collection, variable)
            
            # Cache the result with size limit
            if len(self._cache) > 100:  # Limit cache size
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]['timestamp'])
                del self._cache[oldest_key]
            
            self._cache[cache_key] = {
                'collection': processed_collection,
                'timestamp': datetime.now()
            }
            
            return processed_collection
            
        except Exception as e:
            raise ValueError(f"Error accessing collection: {str(e)}")


    def calculate_index(self, timeframe: TimeFrameType,
                     start_date: str, end_date: str,
                     geometry: ee.Geometry,
                     index_name: str) -> Tuple[ee.Image, IndexInfo]:
        """Calculate a climate index with caching support"""
        try:
            # Get index info and required variables
            index_info = CMIP6Indices.get_index_info(index_name)
            
            # Get required collections based on index category
            if index_info.category == IndexCategory.PRECIPITATION:
                collection = self.get_collection(
                    timeframe, start_date, end_date, geometry, 'precipitation'
                )
            else:  # Temperature indices
                tasmax = self.get_collection(
                    timeframe, start_date, end_date, geometry, 'tasmax'
                )
                tasmin = self.get_collection(
                    timeframe, start_date, end_date, geometry, 'tasmin'
                )
                collection = tasmax.combine(tasmin)
            
            # Calculate the index
            return self.indices_calculator.calculate_index(collection, index_name)
            
        except Exception as e:
            raise ValueError(f"Error calculating index: {str(e)}")

    def get_variable_info(self, variable: str) -> Dict[str, Any]:
        """Get information about a specific variable"""
        variables = {
            'precipitation': {
                'ee_name': 'pr',
                'units': 'mm/day',
                'description': 'Daily precipitation rate',
                'raw_units': 'kg/m^2/s'
            },
            'temperature': {
                'ee_name': 'tas',
                'units': '°C',
                'description': 'Near-surface air temperature',
                'raw_units': 'K'
            },
            'tasmax': {
                'ee_name': 'tasmax',
                'units': '°C',
                'description': 'Daily maximum near-surface air temperature',
                'raw_units': 'K'
            },
            'tasmin': {
                'ee_name': 'tasmin',
                'units': '°C',
                'description': 'Daily minimum near-surface air temperature',
                'raw_units': 'K'
            }
        }
        
        if variable not in variables:
            raise ValueError(f"Unknown variable: {variable}")
        return variables[variable]

    def get_available_indices(self, category: Optional[IndexCategory] = None) -> List[str]:
        """Get list of available climate indices"""
        return CMIP6Indices.list_indices(category)

    def get_index_info(self, index_name: str) -> IndexInfo:
        """Get information about a specific index"""
        return CMIP6Indices.get_index_info(index_name)

    def get_visualization_params(self, index_name: str) -> Dict:
        """Get visualization parameters for an index"""
        return self.indices_calculator.get_visualization_params(index_name)

    def cleanup(self):
        """Clean up resources and clear cache"""
        self._cache.clear()
        self._geometry_hashes.clear()