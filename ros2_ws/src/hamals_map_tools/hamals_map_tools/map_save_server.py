#!/usr/bin/env python3

import os
import re
import subprocess
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


DEFAULT_MAP_DIRECTORY = (
    "/home/hamal/hamal_eski_pi/hamal_agv/"
    "ros2_ws/src/hamals_slam/maps"
)

DEFAULT_MAP_NAME = "hamal_map"


class MapSaveServer(Node):

    def __init__(self):
        super().__init__("hamal_map_save_server")

        # Launch dosyasından değiştirilebilecek parametreler.
        self.declare_parameter(
            "map_directory",
            DEFAULT_MAP_DIRECTORY
        )

        self.declare_parameter(
            "map_name",
            DEFAULT_MAP_NAME
        )

        self.declare_parameter(
            "save_timeout",
            15.0
        )

        self._save_lock = threading.Lock()

        self._service = self.create_service(
            Trigger,
            "/hamal/save_map",
            self.save_map_callback
        )

        map_directory = self.get_parameter(
            "map_directory"
        ).get_parameter_value().string_value

        map_name = self.get_parameter(
            "map_name"
        ).get_parameter_value().string_value

        self.get_logger().info(
            "Harita kaydetme servisi hazır."
        )

        self.get_logger().info(
            "Servis: /hamal/save_map"
        )

        self.get_logger().info(
            f"Hedef: {map_directory}/{map_name}"
        )

    def save_map_callback(self, request, response):
        del request

        # Kullanıcı art arda butona basarsa aynı anda iki kayıt başlamasın.
        if not self._save_lock.acquire(blocking=False):
            response.success = False
            response.message = "Harita zaten kaydediliyor."
            return response

        try:
            map_directory_text = self.get_parameter(
                "map_directory"
            ).get_parameter_value().string_value

            map_name = self.get_parameter(
                "map_name"
            ).get_parameter_value().string_value

            save_timeout = self.get_parameter(
                "save_timeout"
            ).get_parameter_value().double_value

            # Dosya adı yalnızca güvenli karakterlerden oluşsun.
            if not re.fullmatch(r"[A-Za-z0-9_-]+", map_name):
                response.success = False
                response.message = (
                    "Geçersiz harita adı. "
                    "Yalnızca harf, rakam, alt çizgi ve tire kullanılabilir."
                )
                return response

            map_directory = Path(map_directory_text).expanduser().resolve()
            map_directory.mkdir(parents=True, exist_ok=True)

            map_prefix = map_directory / map_name

            command = [
                "ros2",
                "run",
                "nav2_map_server",
                "map_saver_cli",
                "-f",
                str(map_prefix),
                "--ros-args",
                "-p",
                f"save_map_timeout:={save_timeout}",
            ]

            self.get_logger().info(
                f"Harita kaydediliyor: {map_prefix}"
            )

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=max(30.0, save_timeout + 10.0),
                env=os.environ.copy(),
                check=False,
            )

            yaml_file = map_prefix.with_suffix(".yaml")
            pgm_file = map_prefix.with_suffix(".pgm")

            if result.returncode == 0 and yaml_file.exists():
                response.success = True
                response.message = (
                    f"Harita başarıyla kaydedildi: {yaml_file}"
                )

                self.get_logger().info(response.message)

                if pgm_file.exists():
                    self.get_logger().info(
                        f"Harita görseli: {pgm_file}"
                    )

                return response

            error_message = result.stderr.strip()

            if not error_message:
                error_message = result.stdout.strip()

            if not error_message:
                error_message = (
                    f"map_saver_cli çıkış kodu: {result.returncode}"
                )

            # Web paneline devasa terminal çıktısı göndermeyelim.
            error_message = error_message[-800:]

            response.success = False
            response.message = (
                f"Harita kaydedilemedi: {error_message}"
            )

            self.get_logger().error(response.message)
            return response

        except subprocess.TimeoutExpired:
            response.success = False
            response.message = (
                "Harita kaydetme zaman aşımına uğradı. "
                "/map konusu yayınlanıyor mu kontrol et."
            )

            self.get_logger().error(response.message)
            return response

        except Exception as error:
            response.success = False
            response.message = (
                f"Beklenmeyen hata: {error}"
            )

            self.get_logger().exception(response.message)
            return response

        finally:
            self._save_lock.release()


def main(args=None):
    rclpy.init(args=args)

    node = MapSaveServer()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
