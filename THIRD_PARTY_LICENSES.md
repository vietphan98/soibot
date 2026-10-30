# Giấy phép bên thứ ba

soibot không chép mã của dự án khác; chỉ dùng các thư viện sau làm phụ thuộc:

| Thư viện | Giấy phép | Dùng cho |
|---|---|---|
| pandas | BSD-3-Clause | xử lý chuỗi giá |
| numpy | BSD-3-Clause | tính toán |
| requests | Apache-2.0 | gọi API giá |
| pytest (chỉ khi test) | MIT | kiểm thử |

Dữ liệu giá © VNDirect và Yahoo Finance, chỉ dùng cá nhân/phi thương mại; soibot không liên kết với các đơn vị này.
Repo **không** phân phối lại giá thật: giá chỉ được tải về cache trên máy người dùng. Dữ liệu demo trong repo
(`--source gialap`, `soibot/synthetic.py`) là **DỮ LIỆU GIẢ LẬP, không phải giá thật**.
