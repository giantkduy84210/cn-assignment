import os

def print_full_tree(root_dir, prefix=""):
    """
    In ra toàn bộ cấu trúc thư mục + file.
    """
    # Lấy danh sách tất cả folder và file, sort cho đẹp
    entries = sorted(os.listdir(root_dir))
    for i, entry in enumerate(entries):
        path = os.path.join(root_dir, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + entry)
        
        # Nếu là thư mục, đệ quy
        if os.path.isdir(path):
            new_prefix = prefix + ("    " if i == len(entries) - 1 else "│   ")
            print_full_tree(path, new_prefix)

# -------------------------------
# Ví dụ sử dụng
# -------------------------------
root_path = "."  # Thay bằng thư mục muốn in
print(f"Full tree của: {os.path.abspath(root_path)}\n")
print_full_tree(root_path)
