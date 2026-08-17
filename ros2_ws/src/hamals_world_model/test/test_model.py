from pathlib import Path

from hamals_world_model.model import WorldModel


def test_all_pickup_dropoff_routes_exist():
    profile = Path(__file__).parents[1] / 'config' / 'profiles' / 'competition.yaml'
    model = WorldModel(profile)
    for pickup in ('A1', 'A2', 'A3'):
        for dropoff in ('B1', 'B2', 'B3'):
            route = model.plan_route(
                model.stations[pickup]['approach_node'],
                model.stations[dropoff]['approach_node'],
                True,
            )
            assert route.node_ids


def test_station_geometry_and_qr_bindings_are_valid():
    profile = Path(__file__).parents[1] / 'config' / 'profiles' / 'competition.yaml'
    model = WorldModel(profile)
    assert model.frame_id == 'map'
    assert set(model.stations) == {'A1', 'A2', 'A3', 'B1', 'B2', 'B3'}
    assert all(station['expected_qr'] in model.qr_markers for station in model.stations.values())
