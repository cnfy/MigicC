#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <atomic>
#include <string>

static HMODULE module;
static std::atomic<long> objects{0};
static const CLSID commandId = {0x79dcdf77,0xe582,0x4aa8,{0xba,0xac,0xef,0x6c,0x3e,0x11,0xa7,0x28}};
static std::wstring directory() {
    wchar_t path[32768];
    DWORD length = GetModuleFileNameW(module, path, ARRAYSIZE(path));
    std::wstring result(path, length);
    return result.substr(0, result.find_last_of(L'\\') + 1);
}
static HRESULT selectedFile(IShellItemArray* items, std::wstring& path) {
    DWORD count = 0;
    if (!items || FAILED(items->GetCount(&count)) || count != 1) return E_INVALIDARG;
    IShellItem* item = nullptr;
    HRESULT hr = items->GetItemAt(0, &item);
    if (FAILED(hr)) return hr;
    SFGAOF attributes = 0;
    hr = item->GetAttributes(SFGAO_FOLDER | SFGAO_FILESYSTEM, &attributes);
    if (SUCCEEDED(hr) && (attributes & SFGAO_FILESYSTEM) && !(attributes & SFGAO_FOLDER)) {
        PWSTR name = nullptr;
        hr = item->GetDisplayName(SIGDN_FILESYSPATH, &name);
        if (SUCCEEDED(hr)) { path = name; CoTaskMemFree(name); }
    } else hr = E_INVALIDARG;
    item->Release();
    return hr;
}
class Command final : public IExplorerCommand {
    std::atomic<ULONG> refs{1};
public:
    Command() { ++objects; }
    ~Command() { --objects; }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid == IID_IUnknown || iid == IID_IExplorerCommand) {
            *out = static_cast<IExplorerCommand*>(this); AddRef(); return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG n = --refs; if (!n) delete this; return n; }
    HRESULT STDMETHODCALLTYPE GetTitle(IShellItemArray*, PWSTR* out) override {
        return SHStrDupW(L"用 MagicC 二维码分享", out);
    }
    HRESULT STDMETHODCALLTYPE GetIcon(IShellItemArray*, PWSTR* out) override {
        return SHStrDupW((directory() + L"MagicC.ico").c_str(), out);
    }
    HRESULT STDMETHODCALLTYPE GetToolTip(IShellItemArray*, PWSTR* out) override {
        return SHStrDupW(L"使用手机扫码下载文件", out);
    }
    HRESULT STDMETHODCALLTYPE GetCanonicalName(GUID* out) override {
        if (!out) return E_POINTER; *out = commandId; return S_OK;
    }
    HRESULT STDMETHODCALLTYPE GetState(IShellItemArray* items, BOOL, EXPCMDSTATE* out) override {
        if (!out) return E_POINTER;
        std::wstring file;
        *out = SUCCEEDED(selectedFile(items, file)) ? ECS_ENABLED : ECS_HIDDEN;
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE Invoke(IShellItemArray* items, IBindCtx*) override {
        std::wstring file;
        HRESULT hr = selectedFile(items, file);
        if (FAILED(hr)) return hr;
        std::wstring exe = directory() + L"MagicC.exe";
        std::wstring args = L"\"" + exe + L"\" --share-file \"" + file + L"\"";
        STARTUPINFOW startup{sizeof(startup)};
        PROCESS_INFORMATION process{};
        if (!CreateProcessW(exe.c_str(), args.data(), nullptr, nullptr, FALSE, 0,
                            nullptr, directory().c_str(), &startup, &process))
            return HRESULT_FROM_WIN32(GetLastError());
        CloseHandle(process.hThread); CloseHandle(process.hProcess);
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE GetFlags(EXPCMDFLAGS* out) override {
        if (!out) return E_POINTER; *out = ECF_DEFAULT; return S_OK;
    }
    HRESULT STDMETHODCALLTYPE EnumSubCommands(IEnumExplorerCommand** out) override {
        if (out) *out = nullptr; return E_NOTIMPL;
    }
};
class Factory final : public IClassFactory {
    std::atomic<ULONG> refs{1};
public:
    Factory() { ++objects; }
    ~Factory() { --objects; }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER; *out = nullptr;
        if (iid == IID_IUnknown || iid == IID_IClassFactory) {
            *out = static_cast<IClassFactory*>(this); AddRef(); return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs; }
    ULONG STDMETHODCALLTYPE Release() override { ULONG n = --refs; if (!n) delete this; return n; }
    HRESULT STDMETHODCALLTYPE CreateInstance(IUnknown* outer, REFIID iid, void** out) override {
        if (outer) return CLASS_E_NOAGGREGATION;
        auto command = new Command;
        HRESULT hr = command->QueryInterface(iid, out); command->Release(); return hr;
    }
    HRESULT STDMETHODCALLTYPE LockServer(BOOL lock) override { objects += lock ? 1 : -1; return S_OK; }
};
extern "C" HRESULT __stdcall DllGetClassObject(REFCLSID id, REFIID iid, void** out) {
    if (id != commandId) return CLASS_E_CLASSNOTAVAILABLE;
    auto factory = new Factory;
    HRESULT hr = factory->QueryInterface(iid, out); factory->Release(); return hr;
}
extern "C" HRESULT __stdcall DllCanUnloadNow() { return objects == 0 ? S_OK : S_FALSE; }
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, void*) {
    if (reason == DLL_PROCESS_ATTACH) { module = instance; DisableThreadLibraryCalls(instance); }
    return TRUE;
}
