"""Expose Nav2's map saver as a fixed-destination GUI service."""

import threading
from pathlib import Path

import rclpy
from nav2_msgs.srv import SaveMap
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_srvs.srv import Trigger

from hamals_map_tools.map_files import verify_saved_map


MAP_PREFIX = Path.home() / 'hamal_agv/ros2_ws/src/hamals_slam/maps/default'


class MapSaveServer(Node):
    """Relay /map/save to the lifecycle-managed Nav2 map saver."""

    def __init__(self):
        super().__init__('map_save_service_node')
        group = ReentrantCallbackGroup()
        self._client = self.create_client(
            SaveMap, '/map_saver/save_map', callback_group=group)
        self._service = self.create_service(
            Trigger, '/map/save', self.save_map_callback, callback_group=group)
        self._save_lock = threading.Lock()
        self.get_logger().info(
            f'/map/save ready; destination: {MAP_PREFIX}.yaml')

    def save_map_callback(self, request, response):
        del request
        if not self._save_lock.acquire(blocking=False):
            response.message = 'Harita zaten kaydediliyor.'
            return response
        try:
            directory = MAP_PREFIX.parent
            if not directory.is_dir():
                raise RuntimeError(f'Harita dizini bulunamadı: {directory}')
            if not self._client.wait_for_service(timeout_sec=3.0):
                raise RuntimeError('Nav2 map saver servisi hazır değil.')

            yaml_file = MAP_PREFIX.with_suffix('.yaml')
            pgm_file = MAP_PREFIX.with_suffix('.pgm')
            previous = {p: p.stat().st_mtime_ns if p.exists() else None
                        for p in (yaml_file, pgm_file)}
            save_request = SaveMap.Request()
            save_request.map_topic = '/map'
            save_request.map_url = str(MAP_PREFIX)
            save_request.image_format = 'pgm'
            save_request.map_mode = 'trinary'
            save_request.free_thresh = 0.25
            save_request.occupied_thresh = 0.65

            done = threading.Event()
            future = self._client.call_async(save_request)
            future.add_done_callback(lambda unused: done.set())
            if not done.wait(30.0):
                future.cancel()
                raise RuntimeError('Nav2 map saver zaman aşımına uğradı.')
            saved = future.result()
            if saved is None or not saved.result:
                raise RuntimeError(
                    'Nav2 map saver haritayı kaydedemedi; '
                    '/map yayınını kontrol edin.')
            verify_saved_map(MAP_PREFIX, previous)
            response.success = True
            response.message = f'Map saved to {yaml_file}'
            self.get_logger().info(response.message)
        except Exception as error:
            response.success = False
            response.message = str(error)
            self.get_logger().error(f'Harita kaydedilemedi: {error}')
        finally:
            self._save_lock.release()
        return response


def main(args=None):
    rclpy.init(args=args)
    node = MapSaveServer()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
