#pragma once

#include <vector>
#include <cstddef>

namespace hamals_lidar_toolbox
{
namespace core
{

class ScanData
{
public:
    ScanData(
        std::vector<float> ranges,
        double angle_min,
        double angle_increment,
        double timestamp
    );

    const std::vector<float>& ranges() const;
    double angleMin() const;
    double angleIncrement() const;
    std::size_t size() const;
    double timestamp() const;

private:
    std::vector<float> ranges_;
    double angle_min_;
    double angle_increment_;
    double timestamp_;
};

} // namespace core
} // namespace hamals_lidar_toolbox
