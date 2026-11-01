using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;

namespace PixelArtStudio
{
    internal static class Program
    {
        private const string Host = "127.0.0.1";
        private const int Port = 8765;
        private const string BaseUrl = "http://127.0.0.1:8765";
        private const string MutexName = "PixelArtStudio.Launcher.SingleInstance";

        [STAThread]
        private static void Main(string[] args)
        {
            bool created;
            using (Mutex mutex = new Mutex(true, MutexName, out created))
            {
                if (!created)
                {
                    // Another launcher is already starting the server. Wait briefly
                    // for health, then open the browser instead of starting again.
                    WaitAndOpen();
                    return;
                }

                try
                {
                    Run();
                }
                catch (Exception ex)
                {
                    ShowError(
                        "No se pudo iniciar Pixel Art & Game Asset Studio.",
                        ex.Message + "\n\nTambién puedes ejecutar start.bat para ver los detalles en consola.");
                }
                finally
                {
                    try { mutex.ReleaseMutex(); }
                    catch { }
                }
            }
        }

        private static void Run()
        {
            string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
            string python = Path.Combine(root, Path.Combine("backend", Path.Combine(".venv", Path.Combine("Scripts", "python.exe"))));
            string index = Path.Combine(root, Path.Combine("frontend", Path.Combine("dist", "index.html")));

            if (!File.Exists(python))
            {
                ShowError(
                    "No se encontró el entorno local de Python.",
                    "Abre install.bat una vez para crear backend\\.venv e instalar las dependencias.\n\n" +
                    "Ruta esperada:\n" + python);
                return;
            }

            if (!File.Exists(index))
            {
                BuildFrontend(root);
                if (!File.Exists(index))
                {
                    ShowError(
                        "No se encontró el frontend compilado.",
                        "Ejecuta install.bat (o abre una consola en frontend y ejecuta npm install && npm run build).\n\n" +
                        "Ruta esperada:\n" + index);
                    return;
                }
            }

            if (IsListening())
            {
                if (HealthOk())
                {
                    OpenBrowser();
                    return;
                }

                ShowError(
                    "El puerto " + Port + " ya está ocupado.",
                    "Otra aplicación está usando el puerto " + Port + ". Cierra esa aplicación o cambia el puerto en Ajustes.\n\n" +
                    "Si el estudio ya estaba abierto, prueba http://127.0.0.1:" + Port + " en el navegador.");
                return;
            }

            string dataDir = Path.Combine(root, "data");
            try { Directory.CreateDirectory(dataDir); }
            catch { }

            string logPath = Path.Combine(dataDir, "launcher-server.log");
            string command = "/c \"\"" + python + "\" -m uvicorn app.main:app --host " + Host +
                             " --port " + Port + " --app-dir backend 1>> \"" + logPath + "\" 2>&1\"";

            ProcessStartInfo start = new ProcessStartInfo("cmd.exe", command);
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;

            Process server = Process.Start(start);
            if (server == null)
            {
                ShowError("No se pudo lanzar el servidor local.", "Revisa el archivo " + logPath);
                return;
            }

            Stopwatch watch = Stopwatch.StartNew();
            while (watch.Elapsed.TotalSeconds < 30)
            {
                if (HealthOk())
                {
                    Thread.Sleep(250);
                    OpenBrowser();
                    return;
                }

                if (server.HasExited && !IsListening())
                {
                    ShowError(
                        "El servidor local se cerró durante el arranque.",
                        "Revisa el archivo de diagnóstico:\n" + logPath + "\n\n" +
                        "También puedes ejecutar start.bat para ver el error en la consola.");
                    return;
                }

                Thread.Sleep(300);
            }

            ShowError(
                "El servidor local no respondió a tiempo.",
                "Espera unos segundos y vuelve a abrir PixelArtStudio.exe.\n\n" +
                "Diagnóstico: " + logPath);
        }

        private static void BuildFrontend(string root)
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo("cmd.exe", "/c npm run build");
                start.WorkingDirectory = Path.Combine(root, "frontend");
                start.UseShellExecute = false;
                start.CreateNoWindow = true;
                Process build = Process.Start(start);
                if (build != null) build.WaitForExit(180000);
            }
            catch
            {
                // The caller checks whether index.html exists and reports a useful message.
            }
        }

        private static bool IsListening()
        {
            try
            {
                using (TcpClient client = new TcpClient())
                {
                    IAsyncResult result = client.BeginConnect(Host, Port, null, null);
                    if (!result.AsyncWaitHandle.WaitOne(500)) return false;
                    client.EndConnect(result);
                    return true;
                }
            }
            catch
            {
                return false;
            }
        }

        private static bool HealthOk()
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(BaseUrl + "/api/health");
                request.Timeout = 1500;
                request.ReadWriteTimeout = 1500;
                request.Proxy = null;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                using (StreamReader reader = new StreamReader(response.GetResponseStream()))
                {
                    string body = reader.ReadToEnd();
                    return response.StatusCode == HttpStatusCode.OK && body.IndexOf("\"status\":\"ok\"", StringComparison.Ordinal) >= 0;
                }
            }
            catch
            {
                return false;
            }
        }

        private static void WaitAndOpen()
        {
            Stopwatch watch = Stopwatch.StartNew();
            while (watch.Elapsed.TotalSeconds < 8)
            {
                if (HealthOk())
                {
                    OpenBrowser();
                    return;
                }
                Thread.Sleep(250);
            }
            OpenBrowser();
        }

        private static void OpenBrowser()
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo(BaseUrl);
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch
            {
                // Browsing is best-effort; the server is already running.
            }
        }

        private static void ShowError(string message, string detail)
        {
            MessageBox.Show(
                message + "\n\n" + detail,
                "Pixel Art & Game Asset Studio",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
