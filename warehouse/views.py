from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .Logistech_Engine import LogiMaster
from .models import StorageBin


controller = LogiMaster()

@csrf_exempt
def ingest(request):
    """POST: Add a package to the conveyor belt (ID is auto-generated)"""
    if request.method == 'POST':
        data = json.loads(request.body)
        # UPDATED: No tracking_id passed here
        msg = controller.ingest_package(
            size=int(data.get('size')), 
            destination=data.get('destination'),
            is_fragile=data.get('is_fragile', False)
        )
        return JsonResponse({'status': 'success', 'message': msg})

@csrf_exempt
def generate_bins(request):
    """
    Helper to populate DB with dummy bins representing real warehouse locations.
    """
    import random
    StorageBin.objects.all().delete()
    
    sizes = [5, 10, 15, 20, 50, 100, 200]
    
    # Generate realistic warehouse grid: Aisles, Shelves, Levels
    aisles = 4
    sections = 5 
    levels = 3
    
    created_count = 0
    
    for a in range(1, aisles + 1):
        for s in range(1, sections + 1):
            for l in range(1, levels + 1):
                # Example: "Aisle-01-Sect-02-Lvl-1"
                loc_code = f"Aisle-{a:02d}-Sect-{s:02d}-Lvl-{l}"
                
                # Note: 'bin_id' is an AutoField in models.py, so Postgres 
                # automatically assigns ID 1, 2, 3... we don't pass it here.
                StorageBin.objects.create(
                    location_code=loc_code,
                    capacity=random.choice(sizes)
                )
                created_count += 1

    controller.reload_inventory() # Sync Singleton with new DB data
    return JsonResponse({'status': f'Created {created_count} bins with realistic warehouse locations.'})

@csrf_exempt
def process_queue(request):
    """GET: Trigger the 'Best Fit' algorithm for the next item"""
    msg = controller.process_next_item()
    return JsonResponse({'result': msg})

@csrf_exempt
def optimize_load(request):
    """
    POST: Run 'All or Nothing' Backtracking optimization.
    Body: { "capacity": 500 }
    Note: Packages are fetched automatically from Inventory (Bins).
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        capacity = data.get('capacity')
        
        optimization_result = controller.optimize_truck_loading(capacity)
        
        return JsonResponse({
            'truck_capacity': capacity,
            'filled_size': optimization_result['size'],
            'optimized_packages': optimization_result['selection'],
            'space_utilization': f"{(optimization_result['size']/capacity)*100}%",
            'execution_logs': optimization_result.get('execution_logs', [])
        })
