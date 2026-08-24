# AWS Cedar 維運摘要

驗證代碼：`CEDAR-S3-814`

Cedar 服務的唯讀報表位於核准的 S3 prefix。平台負責人是 AWS Operations，
報表更新窗口為每週三 03:30 UTC。這份文件只上傳到 AWS S3，讓 Lab 5 能辨識
窄介面的 `list_objects` 與 `read_object`。
