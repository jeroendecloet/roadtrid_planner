import sys
import json
from typing import Any, Union
from geopy.geocoders import Nominatim
import folium
import numpy as np

import src.dictionary as dictionary


class MapItems:
    """
    Class to easily get and set items in the JSON configuration file.
    """

    def __init__(self, d=None, filename=None):
        if d is None:
            self.d = dict()
        else:
            self.d = d

        self.filename = filename

    def __getitem__(self, keys: Union[list, str]) -> dict:

        if isinstance(keys, str):
            keys = [keys]

        result = self.d
        for key in keys:
            result = result[key]
        return result

    def __setitem__(self, keys: Union[list, str], val: Any) -> None:

        if isinstance(keys, str):
            keys = [keys]

        _d = self[keys[:-1]]

        key = keys[-1]
        # if key in _d.keys() and isinstance(_d[key], dict) and isinstance(val, dict):
        #     _d[key] = {**_d[key], **val}
        # else:
        _d[key] = val

    def get(self, keys: Union[list, str], default: Any):
        """ Mimics the .get() from a Python dict. """
        try:
            return self[keys]
        except KeyError:
            return default

    def to_json(self, filename: str = None) -> None:
        """Saves a json file"""
        if filename is None:
            if self.filename is None:
                raise ValueError("No filename is given, so cannot save MapItems!")
            else:
                filename = self.filename

        with open(filename, 'w') as json_file:
            json.dump(self.d, json_file, indent=4, sort_keys=True)

    @classmethod
    def from_json(cls, filename: str) -> Any:
        """Loads a json file"""
        with open(filename, 'r') as json_file:
            data = json.load(json_file)
        return cls(d=data, filename=filename)


class Locator:
    """
    Class for finding coordinates of locations.
    """
    def __init__(self):
        self.locator = Nominatim(user_agent="GetLoc")

    def __call__(self, *args, **kwargs):
        return self.get_coordinates(*args, **kwargs)

    def get_coordinates(self, location: str, additional_info: str = "") -> list[Union[float, None]]:
        """ Gets the latitude and longitude of a location. Additional information can be supplied, such as a country."""
        _loc_query = ' '.join([location, additional_info])
        print(f"Getting location for {_loc_query}...")
        loc = self.locator.geocode(_loc_query, language='nl')
        if loc is None:
            print(f"{location} not found!")
            return [None, None]
        else:
            print("Success!")
            return [loc.latitude, loc.longitude]


class MapMaker:
    """
    Class to construct the map with all its components.
    """
    def __init__(self, map_item_filename=None, language='nl'):

        if map_item_filename is not None:
            self.mi = MapItems.from_json(map_item_filename)
        else:
            self.mi = MapItems()

        self.locator = Locator()

        self.base_map = None

        if language == "nl":
            self.lg = dictionary.Nederlands.get_names_values()
        elif language == "en":
            self.lg = dictionary.English.get_names_values()

    def create_map(self) -> None:
        self.base_map = folium.Map(location=self.mi['main']['coordinates'], control_scale=True, zoom_start=7, tiles=None)
        folium.TileLayer("CartoDB Voyager", control=False).add_to(self.base_map)

    def _add_marker(self, marker_type: str, name: str, coordinates: list[float], **kwargs: Any) -> None:
        """Add a marker to the in-memory JSON structure."""
        markers = self.mi.d.setdefault("markers", {})
        marker_group = markers.setdefault(marker_type, {})
        marker_group[name] = {"coordinates": coordinates, **kwargs}
        self.mi.to_json()

    def add_restaurant(self, name: str, coordinates: list[float], **kwargs: Any) -> None:
        """Add a restaurant marker and any optional fields."""
        self._add_marker("food", name, coordinates, **kwargs)

    def add_hotel(self, name: str, coordinates: list[float], **kwargs: Any) -> None:
        """Add a hotel marker and any optional fields."""
        self._add_marker("hotel", name, coordinates, **kwargs)

    def add_landmark(self, name: str, coordinates: list[float], **kwargs: Any) -> None:
        """Add a landmark marker and any optional fields."""
        self._add_marker("landmark", name, coordinates, **kwargs)

    def _add_coordinates(self, keys: Union[list, str]) -> None:
        """ Adds coordinates to locations that do not have coordinates yet. """
        if isinstance(keys, str):
            keys = [keys]

        _added_coordinates = False
        for loc in self.mi[keys]:
            if ("coordinates" not in self.mi[keys + [loc]]) or (not self.mi[keys + [loc, "coordinates"]]):
                if "country" in self.mi["main"]:
                    self.mi[keys + [loc, "coordinates"]] = self.locator(loc, self.mi[["main", "country"]])
                else:
                    self.mi[keys + [loc, "coordinates"]] = self.locator(loc)
                _added_coordinates = True

        if _added_coordinates:
            # If any coordinates have been added; save the MapItems to JSON
            self.mi.to_json()

    @staticmethod
    def _create_icon(icon: str, color: str) -> folium.Icon:
        """
        For all available icons, see https://fontawesome.com/icons?d=gallery
        """
        if 'hotel' in icon:
            return folium.Icon(color=color, icon="bed", prefix='fa')
        elif 'landmark' in icon:
            return folium.Icon(color=color, icon='landmark', prefix='fa')
        elif icon == "food":
            return folium.Icon(color=color, icon='utensils', prefix='fa')
        else:
            # Try to make icon
            return folium.Icon(color=color, icon=icon, prefix='fa')

    def _create_popup(self, loc: str, info_dict: dict[str, Any], width: int = 200, height: int = 200) -> folium.Popup:
        """
        Creates popup information for the markers.

        Possibilities (in order):
        - website: Link to the website
        - price: Price of the location
        - info: Free text; will be displayed as-is.
        - availability: List of dates that the location is available
        """

        def _fill_str(str_format: str, info_dict: dict, key: str):
            return str_format.format(**{key: info_dict[key]}) if key in info_dict else ""

        # Info - display as-is
        _info_format = "{info}<br>"

        # Website - create url
        _website_format = """<a href="{website}" target="_blank">%s</a><br>""" % self.lg['website'].capitalize()

        # Price - list the price with corresponding unit OR 'free'
        if 'price' in info_dict.keys():
            if info_dict['price'] == "free":
                _price = "{name}: {price}!<br>".format(
                    name=self.lg['price'].capitalize(),
                    price=self.lg['free']
                )
            else:
                # if "price_unit" in self.mi["main"]:
                #     unit = self.mi[['main', 'price_unit']]
                # else:
                #     unit = "euro"
                unit = self.mi.get(['main', 'price_unit'], "euro")

                _price = "{name}: &{unit}; {price}<br>".format(
                    name=self.lg['price'].capitalize(),
                    unit=unit,
                    price=info_dict['price']
                )
        else:
            _price = ""

        # Availability - make a list of dates
        _availability = "{name}: <ul>{availability}</ul>".format(
            name=self.lg['availability'].capitalize(),
            availability=''.join([f"<li>{item}</li>" for item in info_dict['availability']])
        ) if 'availability' in info_dict else ''

        # Create HTML
        html = """<b>{loc}</b><br>{website}{price}{info}{availability}""".format(
            loc=loc,
            website=_fill_str(_website_format, info_dict, 'website'),
            price=_price,
            info=_fill_str(_info_format, info_dict, 'info'),
            availability=_availability
        )
        return folium.Popup(folium.IFrame(html, width=width, height=height))

    def add_markers(self) -> None:
        markers = self.mi["markers"]
        for item, locations in markers.items():
            self._add_coordinates(["markers", item])
            for loc, info_dict in locations.items():
                assert "coordinates" in info_dict.keys(), f"{loc} is missing coordinates!"

                popup = self._create_popup(loc, info_dict=info_dict)

                colors = {
                    "hotel": "green",
                    "landmark": "red",
                    "food": "blue"
                }

                folium.Marker(
                    location=info_dict["coordinates"],
                    popup=popup,
                    icon=self._create_icon(
                        icon=info_dict['icon'] if 'icon' in info_dict.keys() else item,
                        color=colors[item]
                    )
                ).add_to(self.base_map)

    def zoom(self):
        """ Automatically find the optimal zoom such that all markers are in view. """
        coordinates = []
        markers = self.mi["markers"]
        for item, locations in markers.items():
            for loc, info_dict in locations.items():
                if "coordinates" in info_dict.keys():
                    coordinates.append(info_dict["coordinates"])

        if coordinates:
            sw = np.array(coordinates).min(axis=0).tolist()
            ne = np.array(coordinates).max(axis=0).tolist()
            self.base_map.fit_bounds([sw, ne])

    def save_map(self, filename: str) -> None:
        self.base_map.save(filename)

    def main(self) -> None:
        self.create_map()

        self.add_markers()

        self.zoom()


if __name__ == "__main__":
    json_file = sys.argv[1]

    # Initialize MapMaker object with JSON file
    mm = MapMaker(map_item_filename=json_file)

    # Create map
    mm.main()

    # Save map to HTML
    country = mm.mi.d['country'].capitalize()
    html_file = f"{country}Map.html"
    mm.save_map(html_file)
