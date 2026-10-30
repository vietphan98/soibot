# Giấy phép bên thứ ba

soibot không chép mã của dự án khác; chỉ dùng các thư viện sau làm phụ thuộc:

| Thư viện | Giấy phép | Dùng cho |
|---|---|---|
| pandas | BSD-3-Clause | xử lý chuỗi giá |
| numpy | BSD-3-Clause | tính toán |
| requests | Apache-2.0 | gọi API giá |
| pytest (chỉ khi test) | MIT | kiểm thử |

Dữ liệu giá thuộc quyền của nhà cung cấp gốc (VNDirect, Yahoo Finance). Bộ giá mẫu offline trong
`samples/offline_prices/` chỉ để chạy demo, không phân phối lại cho mục đích thương mại.
