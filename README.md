1. Cấu trúc

```text
EduHub/
├── main.py
├── requirements.txt
├── README.md
├── TuDienMetadata.xlsx
├── metadata_index.json                         
├── <file_id>.json                              
├── input/                                      # Ảnh đầu vào mẫu
│   ├── book01.jpg
│   ├── book02.jpg
│   ├── campus01.jpg
│   ├── campus02.jpg
│   ├── classroom01.png
│   ├── classroom02.png
│   ├── classroom03.png
│   ├── computer01.jpg
│   ├── computer02.jpg
│   ├── event01.jpg
│   ├── event02.jpg
│   ├── lab01.png
│   ├── lab02.png
│   ├── library01.jpeg
│   ├── library02.jpeg
│   ├── student01.jpg
│   ├── student02.jpg
│   ├── student03.jpg
│   ├── student04.jpg
│   ├── student05.jpg
│   ├── invalid.txt
│   ├── duplicates_a/same_name.jpg
│   └── duplicates_b/same_name.jpg
├── data/                                       # Thư mục lưu ảnh sau khi chương trình chạy
│   └── <file_id>.<ext>                         
└── 
```

Lưu ý: Các file <file_id>.json, metadata_index.json và các ảnh trong thư mục data/ không có sẵn khi clone/download project. Đây là các file được chương trình tự động tạo trong quá trình chạy. Thư mục data/ ban đầu có thể để trống.

2. Cài đặt

Cài đặt các thư viện cần thiết:

```bash
python -m pip install -r requirements.txt
```

3. Chạy bằng menu console

Chỉ cần chạy:

```bash
python main.py
```

Chương trình sẽ mở menu tương tác:

```text
====================================================
            EDUHUB IMAGE STORAGE SYSTEM
====================================================
Storage: Local Folder

1. Lưu một ảnh
2. Lưu nhiều ảnh (batch)
3. Tìm kiếm metadata
4. Kiểm tra checksum
5. Xem metadata JSON
6. Xem metadata index
0. Thoát
```

4. Chạy bằng CLI

Chương trình cũng hỗ trợ chạy bằng Command-Line Interface (CLI)

-Lưu một ảnh:

```bash
python main.py "input/book01.jpg" --description "Ảnh sách giáo khoa" --caption "Sách học tập" --tags "book,education"
```

-Lưu nhiều ảnh:

```bash
python main.py "input" --description "Ảnh tài liệu EduHub" --caption "Tài liệu học tập" --tags "education,eduhub"
```

-Kiểm tra checksum:

```bash
python main.py --verify "<file_id>.json"
```

-Tìm kiếm metadata:

```bash
python main.py --search --query "education"
```

-Tìm theo File ID:

```bash
python main.py --search --file-id "<file_id>"
```

-Tìm theo tên file:

```bash
python main.py --search --file-name "book01.jpg"
```

-Tìm theo tag:

```bash
python main.py --search --tag "education"
```

-Tìm theo MIME type:

```bash
python main.py --search --mime-type "image/jpeg"
```