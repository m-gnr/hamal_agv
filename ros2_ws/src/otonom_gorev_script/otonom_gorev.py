#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from hamals_interfaces.msg import ForkCommand
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Twist  # Geri vites için hız komutu kütüphanesi eklendi
import time

class OtonomGorev(Node):
    def __init__(self):
        super().__init__('otonom_gorev_node')
        self.nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        
        self.forklift_pub = self.create_publisher(ForkCommand, '/fork/cmd', 10)
        
        # Otonom sürüş haricinde robota manuel ileri/geri komutu vermek için
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

    def hedefe_git(self, nokta_adi, x, y, z, w):
        self.get_logger().info(f'[{nokta_adi}] Noktasına Gidiliyor: X={x}, Y={y}')
        
        self.nav_client.wait_for_server()
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = float(z)
        goal_msg.pose.pose.orientation.w = float(w)

        send_goal_future = self.nav_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f'[{nokta_adi}] Hedefi reddedildi!')
            return False

        self.get_logger().info('Seyir halinde...')
        get_result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, get_result_future)
        
        status = get_result_future.result().status
        
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'---> [{nokta_adi}] NOKTASINA ULAŞILDI!')
            return True
        else:
            self.get_logger().error(f'HATA! Araç [{nokta_adi}] noktasına gidemedi.')
            return False

    def forklift_calistir(self, yon):
        msg = ForkCommand()
        if yon == 'YUKARI':
            msg.command = 1 # UP
            self.get_logger().info('Forklift komutu: YUKARI KALIYOR')
        elif yon == 'ASAGI':
            msg.command = 2 # DOWN
            self.get_logger().info('Forklift komutu: ASAGI İNİYOR')
        else:
            msg.command = 0 # STOP
            
        self.forklift_pub.publish(msg)
        time.sleep(5.0) 
        self.get_logger().info('Forklift işlemi bitti.')

    def geri_geri_cik(self, sure_saniye=4.0, hiz=-0.2):
        self.get_logger().info('DİKKAT: Palete çarpmamak için geri geri çıkılıyor...')
        twist = Twist()
        twist.linear.x = hiz # Negatif hız (Geri)
        twist.angular.z = 0.0
        
        baslangic = self.get_clock().now()
        # Belirtilen saniye boyunca aralıksız geri komutu bas
        while (self.get_clock().now() - baslangic).nanoseconds / 1e9 < sure_saniye:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)
            
        # Süre bitince robotu durdur
        twist.linear.x = 0.0
        self.cmd_vel_pub.publish(twist)
        self.get_logger().info('Geri manevra tamamlandı, güvenli bölgedeyiz.')

def main(args=None):
    rclpy.init(args=args)
    gorev = OtonomGorev()
    gorev.get_logger().info('--- GÖREV BAŞLADI ---')

    # 1. BAŞLANGIÇ (HOME) KURULUMU: x=0.5, y=-1.3, Sola dönük (z=0.707, w=0.707)
    if gorev.hedefe_git("HOME (HAZIRLIK)", 0.5, -1.3, 0.707, 0.707):
        gorev.forklift_calistir('ASAGI') # En dibe indir
        
        # 2. A1 NOKTASINA GİDİŞ: x=0.5, y=1.3, Sola dönük (z=0.707, w=0.707)
        if gorev.hedefe_git("A1 (YUK ALMA)", 0.5, 1.3, 0.707, 0.707):
            gorev.forklift_calistir('YUKARI') # Yükü al
            
            # 3. B2 NOKTASINA GİDİŞ: x=4.3, y=0.0, İleri dönük (z=0.0, w=1.0)
            if gorev.hedefe_git("B2 (YUK BIRAKMA)", 4.3, 0.0, 0.0, 1.0):
                gorev.forklift_calistir('ASAGI') # Yükü bırak
                
                # 4. PALETTEN GERİ ÇIKARAK KURTULMA
                # Robotu 4 saniye boyunca -0.2 hızında geriye doğru sürer
                gorev.geri_geri_cik(sure_saniye=4.0, hiz=-0.2)
                
                # 5. GERİ ÇIKTIKTAN SONRA HOME'A DÖNÜŞ (Aynı Home Koordinatları)
                gorev.hedefe_git("HOME (DONUS)", 0.5, -1.3, 0.707, 0.707)

    gorev.get_logger().info('--- TÜM OPERASYON BİTTİ ---')
    gorev.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
