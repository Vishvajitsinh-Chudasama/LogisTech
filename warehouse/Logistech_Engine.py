import threading
import bisect
from abc import ABC, abstractmethod 
from collections import deque
from django.db import transaction
from .models import StorageBin, ShipmentLog, Package

class StorageUnit(ABC):
    """
    Abstract Base Class for Bins and Trucks.
    Defines the contract for space management.
    """

    @abstractmethod
    def occupy_space(self, amount):
        """Attempts to reserve space in Bins and Trucks.
        Returns True if successful."""
        raise NotImplementedError
    
    @abstractmethod
    def free_space(self):
        """Clears or reset space in the Bins and Trucks."""
        raise NotImplementedError


class InMemoryBin(StorageUnit):
    """
    A lightweight class for the Binary Search Algorithm(For Find best Bin for Package).
    Represents a Bin in the warehouse.
    """
    def __init__(self, bin_id, capacity, location_code):
        self.bin_id = bin_id
        self.capacity = capacity
        self.location_code = location_code
        self.is_occupied = False

    def __lt__(self, other) -> bool:
        """Crucial for Binary Search: Sort by Capacity"""
        return self.capacity < other.capacity

    def occupy_space(self, amount) -> bool:
        if self.is_occupied or amount > self.capacity:
            return False
        self.is_occupied = True
        return True

    def free_space(self)-> None:
        self.is_occupied = False


class Truck(StorageUnit):
    """
    Represents the Delivery Truck.
    Manages a LIFO stack of packages and tracks volume capacity.
    """
    def __init__(self, capacity=1000):
        self.capacity = capacity
        self.used_space = 0
        self.stack = [] # Follow LIFO Manner as STACK Data Structure

    def occupy_space(self, amount) -> bool:
        if self.used_space + amount > self.capacity:
            return False
        self.used_space += amount
        return True

    def free_space(self) -> None:
        self.stack = []
        self.used_space = 0

    def load(self, tracking_id, size) -> bool:
        """ Add Data on the top of the stack. """
        if self.occupy_space(size):
            self.stack.append({'id': tracking_id, 'size': size})
            return True
        return False

    def pop(self) -> int:
        """ Remove data from the top of the stack. """
        if not self.stack:
            return None
        item = self.stack.pop()
        self.used_space -= item['size']
        return item

class LogiMaster:
    """
    The 'Control Tower'.
    Implements the Singleton Pattern to ensure one source of truth.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LogiMaster, cls).__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        print("Initializing LogiMaster Control Tower...")
        self.conveyor_queue = deque()
        self.truck = Truck(capacity=2000)
        self.reload_inventory()

    def reload_inventory(self):
        """Loads bins from SQL and sorts them for O(log N) search."""
        try:
            db_bins = StorageBin.objects.filter(is_occupied=False).order_by('capacity')
            self.bin_inventory = [
                InMemoryBin(b.bin_id, b.capacity, b.location_code) 
                for b in db_bins
            ]
            self.bin_inventory.sort()
        except:
            print("Warning: Database tables not ready. Inventory init skipped.")
            self.bin_inventory = []

    def ingest_package(self, size, destination, is_fragile=False):
        """
        Creates a package with an auto-generated tracking ID 
        and adds it to the Conveyor queue (FIFO manner follow).
        """
        pkg = Package.objects.create(
            size=size, 
            destination=destination, 
            is_fragile=is_fragile
        )
        
        self.conveyor_queue.append(pkg) # Add data at last and remove from the front as queue data Structure
        
        ShipmentLog.objects.create(
            tracking_id=pkg.tracking_id,
            status='INGESTED',
            details=f"Size: {size}, Fragile: {is_fragile}"
        )
        return f"Package {pkg.tracking_id} generated and added to conveyor."

    def find_best_fit_bin(self, package_size):
        """ Find the best fit bin for package size within O(log N) Binary Search. """
        dummy_search_key = InMemoryBin(None, package_size, None)
        index = bisect.bisect_left(self.bin_inventory, dummy_search_key)
        if index < len(self.bin_inventory):
            return self.bin_inventory[index]
        return None

    def process_next_item(self):
        """ Queue implementaion
        and find the best bin for package which is in the front
        and update memory and DB using transection method
        Now the pacakage store in bin using queue."""
        if not self.conveyor_queue: return "Conveyor is empty."
        pkg = self.conveyor_queue[0]
        
        best_bin = self.find_best_fit_bin(pkg.size)
        if not best_bin:
            requeued_pkg = self.conveyor_queue.popleft() 
            self.conveyor_queue.append(requeued_pkg)
            return f"No suitable bin found for size {pkg.size}"

        try:
            with transaction.atomic():
                db_bin = StorageBin.objects.select_for_update().get(bin_id=best_bin.bin_id)
                db_bin.is_occupied = True
                db_bin.current_tracking_id = pkg.tracking_id
                db_bin.save()
                
                best_bin.occupy_space(pkg.size) 
                
                ShipmentLog.objects.create(tracking_id=pkg.tracking_id, bin_id=db_bin.bin_id, status='STORED', details=f"Stored in {db_bin.location_code}")
                self.conveyor_queue.popleft() 
                self.bin_inventory.remove(best_bin)
                return f"Stored {pkg.tracking_id} in {best_bin.location_code}"
        except Exception as e:
            return f"System Error: {str(e)}"

    def optimize_truck_loading(self, truck_capacity):
        """
        1. FETCH: Finds all packages currently stored in bins using 'current_tracking_id'.
        2. ALGORITHM: Calculates optimal 'All or Nothing' fragile loading plan.
        3. EXECUTION: Moves selected packages from Bins -> Truck.
        """
        
        valid_packages = []
        
        occupied_bins = StorageBin.objects.filter(is_occupied=True)
        
        for bin_obj in occupied_bins:
            if bin_obj.current_tracking_id:
                try:
                    pkg = Package.objects.get(tracking_id=bin_obj.current_tracking_id)
                    valid_packages.append({
                        'tracking_id': pkg.tracking_id,
                        'size': pkg.size,
                        'is_fragile': pkg.is_fragile
                    })
                except Package.DoesNotExist:
                    continue

        if not valid_packages:
            return {
                "size": 0, 
                "selection": [], 
                "execution_logs": ["Warehouse is empty or no packages found in bins."]
            }

        fragile = [p for p in valid_packages if p.get('is_fragile', False)]
        standard = [p for p in valid_packages if not p.get('is_fragile', False)]

        fragile_total_size = sum(p['size'] for p in fragile)
        
        best_scenario = {"size": 0, "selection": []}

        if fragile_total_size > 0 and fragile_total_size <= truck_capacity:
            remaining_cap = truck_capacity - fragile_total_size
            best_std_size, best_std_pkg = self._find_max_subset(remaining_cap, standard)
            
            total_size_1 = fragile_total_size + best_std_size
            selection_1 = fragile + best_std_pkg
            
            if total_size_1 > best_scenario["size"]:
                best_scenario = {"size": total_size_1, "selection": selection_1}

        best_std_size_only, best_std_pkg_only = self._find_max_subset(truck_capacity, standard)
        
        if best_std_size_only > best_scenario["size"]:
            best_scenario = {"size": best_std_size_only, "selection": best_std_pkg_only}

        execution_logs = []
        for pkg_data in best_scenario['selection']:
            tsize = pkg_data.get('size')
            tid = pkg_data.get('tracking_id')
            if tid:
                bin_freed = self._free_bin_for_package(tid)

                self.truck.load(tid,tsize)
                
                status_msg = "Moved from Bin to Truck" if bin_freed else "Loaded to Truck (was not in bin)"
                execution_logs.append(f"{tid}: {status_msg}")

                ShipmentLog.objects.create(
                    tracking_id=tid,
                    status='LOADED',
                    details=f"{status_msg} (Optimization)"
                )

        best_scenario['execution_logs'] = execution_logs
        return best_scenario

    def _find_max_subset(self, capacity, items):
        if capacity == 0 or not items:
            return 0, []

        current_item = items[0]
        remaining_items = items[1:]
        
        size_without, pkg_without = self._find_max_subset(capacity, remaining_items)
        
        size_with = 0
        pkg_with = []
        if current_item['size'] <= capacity:
            sub_size, sub_pkg = self._find_max_subset(capacity - current_item['size'], remaining_items)
            size_with = current_item['size'] + sub_size
            pkg_with = [current_item] + sub_pkg

        if size_with > size_without:
            return size_with, pkg_with
        else:
            return size_without, pkg_without

    def _free_bin_for_package(self, tracking_id):
        """
        Finds the bin containing the package using current_tracking_id, 
        frees it in DB, and adds it back to the sorted memory list.
        """
        try:
            db_bin = StorageBin.objects.get(current_tracking_id=tracking_id)
            
            if db_bin.is_occupied:
                db_bin.is_occupied = False
                db_bin.current_tracking_id = None
                db_bin.save()

                restored_bin = InMemoryBin(db_bin.bin_id, db_bin.capacity, db_bin.location_code)
                bisect.insort(self.bin_inventory, restored_bin)
                return True
        except StorageBin.DoesNotExist:
            pass
        return False

    def load_truck_item(self, tracking_id):
        try:
            pkg = Package.objects.get(tracking_id=tracking_id)
        except Package.DoesNotExist:
            return f"Error: Package {tracking_id} does not exist."

        if self.truck.load(pkg.tracking_id, pkg.size):
            ShipmentLog.objects.create(tracking_id=tracking_id, status='LOADED')
            return f"Loaded {tracking_id} (Size: {pkg.size})"
        else:
            return "Error: Truck is full."


    def rollback_load(self, target_tracking_id):
        """ Remove specific package from truck using stack
        First unload the truck until did't find the traget package and remove package then reload the truck"""
        if not any(item['id'] == target_tracking_id for item in self.truck.stack):
             return [f"Error: Item {target_tracking_id} not found on truck."]

        temp_storage = []
        action_log = []

        while self.truck.stack:
            item = self.truck.pop()
            current_id = item['id']
            
            if current_id == target_tracking_id:
                ShipmentLog.objects.create(tracking_id=current_id, status='UNLOADED', details="Target item removed via Rollback")
                action_log.append(f"TARGET REMOVED: {current_id}")
                break
            else:
                temp_storage.append(item)
                ShipmentLog.objects.create(tracking_id=current_id, status='UNLOADED', details="Temporarily unloaded")
                action_log.append(f"Temporarily Unloaded: {current_id}")

        while temp_storage:
            item = temp_storage.pop()
            self.truck.load(item['id'], item['size'])
            ShipmentLog.objects.create(tracking_id=item['id'], status='LOADED', details="Reloaded after rollback")
            action_log.append(f"Reloaded: {item['id']}")

        return action_log