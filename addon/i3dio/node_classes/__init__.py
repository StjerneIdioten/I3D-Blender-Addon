if "bpy" in locals():
    import importlib
    reloadable_modules = [
        'file',
        'material',
        'node',
        'shape',
        'merge_group',
        'skinned_mesh'
    ]

    for module_name in reloadable_modules:
        if module_name in locals():
            importlib.reload(locals()[module_name])

# def reload_package(module_dict_main):
#     import importlib
#     from pathlib import Path
#
#     def reload_package_recursive(current_dir, module_dict):
#         for path in current_dir.iterdir():
#             if "__init__" in str(path) or path.stem not in module_dict:
#                 continue
#
#             if path.is_file() and path.suffix == ".py":
#                 importlib.reload(module_dict[path.stem])
#             elif path.is_dir():
#                 reload_package_recursive(path, module_dict[path.stem].__dict__)
#
#     reload_package_recursive(Path(__file__).parent, module_dict_main)
#
#
# if "bpy" in locals():
#     reload_package(locals())

import bpy
