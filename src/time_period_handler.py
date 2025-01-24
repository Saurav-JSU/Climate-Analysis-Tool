"""
time_period_handler.py
Enhanced time period selection and validation for CMIP6 analysis
"""

from typing import Dict, Tuple, Optional, Callable, List
from ipywidgets import widgets, VBox, HBox, Layout, HTML, Button
from datetime import datetime
from dataclasses import dataclass
from IPython.display import display

@dataclass
class TimePeriodSelection:
    """Stores selected time periods"""
    historical_start: int
    historical_end: int
    near_future_start: int
    near_future_end: int
    far_future_start: int
    far_future_end: int

    def to_dict(self) -> Dict[str, Dict[str, int]]:
        """Convert selection to dictionary format"""
        return {
            'historical': {
                'start': self.historical_start,
                'end': self.historical_end
            },
            'near_future': {
                'start': self.near_future_start,
                'end': self.near_future_end
            },
            'far_future': {
                'start': self.far_future_start,
                'end': self.far_future_end
            }
        }

class TimePeriodHandler:
    """
    Enhanced handler for time period selection and validation
    """
    
    # CMIP6 data range information
    HISTORICAL_RANGE = (1980, 2014)
    FUTURE_RANGE = (2015, 2100)
    MIN_PERIOD_LENGTH = 20  # Minimum period length in years
    
    def __init__(self):
        """Initialize TimePeriodHandler"""
        self.current_selection: Optional[TimePeriodSelection] = None
        self._callback: Optional[Callable] = None
        self._error_widget = HTML(
            value="",
            layout=Layout(margin='10px 0px')
        )
        self._period_widgets: Dict[str, Dict[str, widgets.Widget]] = {}
        self._validation_status = {
            'historical': False,
            'near_future': False,
            'far_future': False
        }

    def create_selection_widgets(self) -> widgets.VBox:
        """Create enhanced widgets for time period selection"""
        # Header with explanation
        header = HTML(
            value="""
            <div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>
                <h3 style='margin-top: 0;'>Time Period Selection</h3>
                <p>Please select analysis time periods following these guidelines:</p>
                <ul>
                    <li>Historical period: 1980-2014</li>
                    <li>Near Future period: 2015-2060</li>
                    <li>Far Future period: 2061-2100</li>
                    <li>Each period must span at least 20 years</li>
                </ul>
            </div>
            """
        )
        
        # Create period sections
        periods_container = self._create_period_sections()
        
        # Create validation status display
        validation_status = HTML(
            value="",
            layout=Layout(margin='10px 0px')
        )
        
        # Create submit button
        submit_button = Button(
            description='Continue to Next Step',
            button_style='primary',
            disabled=True,
            layout=Layout(width='200px', margin='20px 0px')
        )
        
        def on_submit(b):
            try:
                if self.current_selection and self._callback:
                    self._callback(self.current_selection)
            except Exception as e:
                self._error_widget.value = f'<p style="color: red">Error: {str(e)}</p>'
        
        submit_button.on_click(on_submit)
        
        def update_validation_status():
            """Update validation status display and submit button"""
            if all(self._validation_status.values()):
                validation_status.value = """
                    <div style='color: green; padding: 10px; border: 1px solid green; 
                         border-radius: 5px; margin: 10px 0;'>
                        ✓ All time periods are valid
                    </div>
                """
                submit_button.disabled = False
            else:
                invalid_periods = [
                    period.replace('_', ' ').title()
                    for period, status in self._validation_status.items()
                    if not status
                ]
                if invalid_periods:
                    validation_status.value = f"""
                        <div style='color: #856404; background-color: #fff3cd; 
                             padding: 10px; border: 1px solid #ffeeba; border-radius: 5px; 
                             margin: 10px 0;'>
                            Please check the following periods: {', '.join(invalid_periods)}
                        </div>
                    """
                submit_button.disabled = True

        # Create main container
        container = VBox([
            header,
            periods_container,
            validation_status,
            submit_button,
            self._error_widget
        ], layout=Layout(width='100%', padding='20px'))
        
        # Store update function
        self._update_validation_status = update_validation_status
        
        return container

    def _create_period_sections(self) -> widgets.VBox:
        """Create sections for each time period"""
        period_configs = {
            'historical': {
                'title': 'Historical Period',
                'range': self.HISTORICAL_RANGE,
                'description': 'Select years from the historical record (1980-2014)'
            },
            'near_future': {
                'title': 'Near Future Period',
                'range': (2015, 2060),
                'description': 'Select years for near-term projections (2015-2060)'
            },
            'far_future': {
                'title': 'Far Future Period',
                'range': (2061, 2100),
                'description': 'Select years for long-term projections (2061-2100)'
            }
        }
        
        period_sections = []
        
        for period_key, config in period_configs.items():
            section = self._create_period_section(
                period_key,
                config['title'],
                config['range'],
                config['description']
            )
            period_sections.append(section)
        
        return VBox(period_sections)

    def _create_period_section(self, period_key: str, title: str, 
                             year_range: Tuple[int, int], 
                             description: str) -> widgets.VBox:
        """Create widgets for a single time period section"""
        # Create sliders
        start_year = widgets.IntSlider(
            value=year_range[0],
            min=year_range[0],
            max=year_range[1] - self.MIN_PERIOD_LENGTH,
            description='Start Year:',
            style={'description_width': 'initial'},
            layout=Layout(width='400px')
        )
        
        end_year = widgets.IntSlider(
            value=year_range[1],
            min=year_range[0] + self.MIN_PERIOD_LENGTH,
            max=year_range[1],
            description='End Year:',
            style={'description_width': 'initial'},
            layout=Layout(width='400px')
        )
        
        # Status indicator
        status_indicator = HTML(value="")
        
        def update_status():
            """Update status for this period"""
            try:
                # Validate period
                start = start_year.value
                end = end_year.value
                
                if end - start + 1 < self.MIN_PERIOD_LENGTH:
                    raise ValueError(f"Period must be at least {self.MIN_PERIOD_LENGTH} years")
                
                # Update validation status
                self._validation_status[period_key] = True
                status_indicator.value = """
                    <div style='color: green; margin: 5px 0;'>
                        ✓ Valid selection
                    </div>
                """
                
                # Update selection
                self._update_period_selection(period_key, start, end)
                
            except Exception as e:
                self._validation_status[period_key] = False
                status_indicator.value = f"""
                    <div style='color: #dc3545; margin: 5px 0;'>
                        ⚠ {str(e)}
                    </div>
                """
            
            # Update overall validation status
            if hasattr(self, '_update_validation_status'):
                self._update_validation_status()
        
        # Add observers
        start_year.observe(lambda _: update_status(), names='value')
        end_year.observe(lambda _: update_status(), names='value')
        
        # Store widgets for later access
        self._period_widgets[period_key] = {
            'start': start_year,
            'end': end_year,
            'status': status_indicator
        }
        
        # Create section
        section = VBox([
            HTML(f"<h4>{title}</h4>"),
            HTML(f"<p>{description}</p>"),
            start_year,
            end_year,
            status_indicator
        ], layout=Layout(
            padding='10px',
            margin='10px 0',
            border='1px solid #dee2e6',
            border_radius='5px'
        ))
        
        # Trigger initial validation
        update_status()
        
        return section

    def _update_period_selection(self, period_key: str, start_year: int, end_year: int):
        """Update the current selection with new period values"""
        if self.current_selection is None:
            self.current_selection = TimePeriodSelection(
                historical_start=self.HISTORICAL_RANGE[0],
                historical_end=self.HISTORICAL_RANGE[1],
                near_future_start=self.FUTURE_RANGE[0],
                near_future_end=2060,
                far_future_start=2061,
                far_future_end=self.FUTURE_RANGE[1]
            )
        
        if period_key == 'historical':
            self.current_selection.historical_start = start_year
            self.current_selection.historical_end = end_year
        elif period_key == 'near_future':
            self.current_selection.near_future_start = start_year
            self.current_selection.near_future_end = end_year
        elif period_key == 'far_future':
            self.current_selection.far_future_start = start_year
            self.current_selection.far_future_end = end_year

    def validate_periods(self, selection: TimePeriodSelection) -> bool:
        """
        Validate time period selection
        
        Args:
            selection: TimePeriodSelection object
            
        Returns:
            True if periods are valid, raises ValueError otherwise
        """
        # Check historical period
        if not (self.HISTORICAL_RANGE[0] <= selection.historical_start <= selection.historical_end <= self.HISTORICAL_RANGE[1]):
            raise ValueError("Historical period must be within 1980-2014")
        
        # Check near future period
        if not (self.FUTURE_RANGE[0] <= selection.near_future_start <= selection.near_future_end <= self.FUTURE_RANGE[1]):
            raise ValueError("Near future period must be within 2015-2100")
        
        # Check far future period
        if not (self.FUTURE_RANGE[0] <= selection.far_future_start <= selection.far_future_end <= self.FUTURE_RANGE[1]):
            raise ValueError("Far future period must be within 2015-2100")
        
        # Check minimum period lengths
        if (selection.historical_end - selection.historical_start + 1) < self.MIN_PERIOD_LENGTH:
            raise ValueError(f"Historical period must be at least {self.MIN_PERIOD_LENGTH} years")
        if (selection.near_future_end - selection.near_future_start + 1) < self.MIN_PERIOD_LENGTH:
            raise ValueError(f"Near future period must be at least {self.MIN_PERIOD_LENGTH} years")
        if (selection.far_future_end - selection.far_future_start + 1) < self.MIN_PERIOD_LENGTH:
            raise ValueError(f"Far future period must be at least {self.MIN_PERIOD_LENGTH} years")
        
        # Check chronological order
        if not (selection.historical_end < selection.near_future_start < 
                selection.near_future_end < selection.far_future_start):
            raise ValueError("Periods must be in chronological order without overlap")
        
        return True

    def set_callback(self, callback: Callable[[TimePeriodSelection], None]) -> None:
        """Set callback for when time periods are selected"""
        self._callback = callback

    def get_current_selection(self) -> Optional[TimePeriodSelection]:
        """Get current time period selection"""
        return self.current_selection

    def get_formatted_dates(self) -> Dict[str, Tuple[str, str]]:
        """
        Convert current selection to Earth Engine date format
        
        Returns:
            Dictionary mapping period names to (start_date, end_date) tuples
            in YYYY-MM-DD format
            
        Raises:
            ValueError: If no time periods have been selected
        """
        if not self.current_selection:
            raise ValueError("No time periods selected")
            
        return {
            'historical': (
                f"{self.current_selection.historical_start}-01-01",
                f"{self.current_selection.historical_end}-12-31"
            ),
            'near_future': (
                f"{self.current_selection.near_future_start}-01-01",
                f"{self.current_selection.near_future_end}-12-31"
            ),
            'far_future': (
                f"{self.current_selection.far_future_start}-01-01",
                f"{self.current_selection.far_future_end}-12-31"
            )
        }

    def reset(self):
        """Reset handler state"""
        self.current_selection = None
        self._validation_status = {
            'historical': False,
            'near_future': False,
            'far_future': False
        }
        if hasattr(self, '_update_validation_status'):
            self._update_validation_status()