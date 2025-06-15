#include "deepracer_navigation_pkg/deepracer_navigation_node.hpp"

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::executors::MultiThreadedExecutor executor;
    auto node = std::make_shared<deepracer_navigation_pkg::DRNavigationNode>();
    executor.add_node(node);
    executor.spin();
    rclcpp::shutdown();
    return 0;
}