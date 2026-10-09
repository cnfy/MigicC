"""Exercise the built COM server without registering it or launching file sharing."""
import ctypes as c
from pathlib import Path
import tempfile
import uuid


class GUID(c.Structure):
    _fields_ = [('bytes', c.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__((c.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))


def method(pointer, index, result, *args):
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(result, c.c_void_p, *args)(table[index])


def check():
    dll = c.WinDLL(str(Path(__file__).resolve().parents[1] / 'dist/MagicCShell.dll'))
    factory_id = GUID('00000001-0000-0000-C000-000000000046')
    command_id = GUID('79DCDF77-E582-4AA8-BAAC-EF6C3E11A728')
    interface_id = GUID('A08CE4D0-FA25-44AB-B57C-C7B1C323E0B9')
    factory = c.c_void_p()
    assert dll.DllGetClassObject(c.byref(command_id), c.byref(factory_id), c.byref(factory)) == 0
    command = c.c_void_p()
    assert method(factory, 3, c.c_long, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p))(
        factory, None, c.byref(interface_id), c.byref(command)) == 0
    method(factory, 2, c.c_ulong)(factory)
    assert dll.DllCanUnloadNow() == 1
    for index, expected in [(3, '用 MagicC 二维码分享'), (4, 'MagicC.ico')]:
        text = c.c_void_p()
        assert method(command, index, c.c_long, c.c_void_p, c.POINTER(c.c_void_p))(command, None, c.byref(text)) == 0
        assert c.wstring_at(text).endswith(expected)
        c.windll.ole32.CoTaskMemFree.argtypes = [c.c_void_p]
        c.windll.ole32.CoTaskMemFree(text)
    state = c.c_int()
    get_state = method(command, 7, c.c_long, c.c_void_p, c.c_int, c.POINTER(c.c_int))
    assert get_state(command, None, False, c.byref(state)) == 0 and state.value == 2
    c.windll.ole32.CoInitialize(None)
    shell = c.windll.shell32
    shell.SHCreateItemFromParsingName.argtypes = [c.c_wchar_p, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p)]
    shell.SHCreateShellItemArrayFromShellItem.argtypes = [c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p)]
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / '测试文件.txt'
        file.write_text('test', encoding='utf-8')
        for path, expected in [(file, 0), (Path(directory), 2)]:
            item, items = c.c_void_p(), c.c_void_p()
            iid_item = GUID('43826D1E-E718-42EE-BC55-A1E261C37BFE')
            iid_array = GUID('B63EA76D-1F85-456F-A19C-48159EFA858B')
            assert shell.SHCreateItemFromParsingName(str(path), None, c.byref(iid_item), c.byref(item)) == 0
            assert shell.SHCreateShellItemArrayFromShellItem(item, c.byref(iid_array), c.byref(items)) == 0
            assert get_state(command, items, False, c.byref(state)) == 0 and state.value == expected
            method(items, 2, c.c_ulong)(items)
            method(item, 2, c.c_ulong)(item)
    method(command, 2, c.c_ulong)(command)
    assert dll.DllCanUnloadNow() == 0
    c.windll.ole32.CoUninitialize()
    print('Native menu: factory, title, icon, file/folder state, unload passed')


if __name__ == '__main__':
    check()
