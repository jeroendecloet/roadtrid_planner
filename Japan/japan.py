from src.main import MapMaker

if __name__ == "__main__":
    # Initialize MapMaker object with JSON file
    mm = MapMaker(map_item_filename="japan_map_items.json")

    # Create map
    mm.main()

    # Save map to HTML
    mm.save_map("JapanMap.html")
