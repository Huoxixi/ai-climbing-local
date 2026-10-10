using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class WindowsApp {
    internal const string Version = "0.1.15-setup.20261010";
    internal static readonly string Cache = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ClimbSetup", Version);
    internal static string Quote(string text) { return "\"" + text.Replace("\"", "\\\"") + "\""; }
    [STAThread] static int Main(string[] args) {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
#if LAUNCHER
        return Launch();
#else
        try {
            if(args.Length == 2 && args[0] == "--extract-to") { Extract(args[1]); return 0; }
            bool first;
            using(var mutex = new Mutex(true, "Local\\AiClimbingCommunitySetup-" + Environment.UserName, out first)) {
                if(!first) { MessageBox.Show("另一个安装窗口已打开，请在那个窗口继续。", "攀岩助手安装"); return 1; }
                Application.Run(new InstallForm());
            }
            return 0;
        } catch(Exception) { MessageBox.Show("安装器启动失败。请检查磁盘空间，并重新下载官方安装包。", "攀岩助手安装", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
#endif
    }
    static int Launch() {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AiClimbingCommunitySetup");
        Directory.CreateDirectory(logDir);
        string log = Path.Combine(logDir, "启动日志.txt");
        bool first;
        using(var mutex = new Mutex(true,"Local\\AiClimbingCommunityApp-"+Environment.UserName,out first)) {
            if(!first) { MessageBox.Show("攀岩助手已经打开，请返回现有窗口。", "攀岩助手"); return 0; }
            try {
                var info = new ProcessStartInfo(Path.Combine(root,"runtime","python.exe"), Quote(Path.Combine(root,"run-local.py")));
                info.WorkingDirectory=root; info.UseShellExecute=false; info.CreateNoWindow=true;
                info.RedirectStandardOutput=true; info.RedirectStandardError=true;
                info.StandardOutputEncoding=Encoding.UTF8; info.StandardErrorEncoding=Encoding.UTF8;
                foreach(string key in new string[]{"PYTHONHOME","PYTHONPATH","VIRTUAL_ENV"}) info.EnvironmentVariables.Remove(key);
                info.EnvironmentVariables["PYTHONUTF8"]="1"; info.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
                using(var writer=new StreamWriter(log,false,Encoding.UTF8))
                using(var process=new Process()) {
                    var gate=new object(); process.StartInfo=info;
                    DataReceivedEventHandler append=(s,e)=>{if(e.Data!=null) lock(gate) { writer.WriteLine(e.Data); writer.Flush(); }};
                    process.OutputDataReceived+=append; process.ErrorDataReceived+=append;
                    process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit();
                    if(process.ExitCode!=0) {
                        MessageBox.Show("程序没有成功打开。请重试；仍失败时到项目 Issues 反馈，并附上启动日志：\n"+log,"攀岩助手",MessageBoxButtons.OK,MessageBoxIcon.Error);
                        return 1;
                    }
                }
                return 0;
            } catch(Exception) { MessageBox.Show("程序文件缺失或无法运行，请重新运行官方安装包。个人资料不需要删除。", "攀岩助手",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1; }
        }
    }
    internal static void Extract(string destination) {
        Directory.CreateDirectory(destination);
        string root=Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
        using(var resource=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using(var archive=new ZipArchive(resource,ZipArchiveMode.Read)) {
            foreach(var item in archive.Entries) {
                string name=item.FullName.Replace('/',Path.DirectorySeparatorChar);
                string path=Path.GetFullPath(Path.Combine(root,name));
                if(!path.StartsWith(root,StringComparison.OrdinalIgnoreCase)||name.Contains(":")) throw new InvalidDataException();
                if(item.FullName.EndsWith("/")) continue;
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using(var input=item.Open()) using(var output=File.Create(path)) input.CopyTo(output);
            }
        }
    }
}

internal sealed class InstallForm : Form {
    readonly Label step=new Label(); readonly Label detail=new Label();
    readonly ProgressBar progress=new ProgressBar(); readonly Button main=new Button();
    readonly LinkLabel logs=new LinkLabel(); string app; bool running; bool completed; bool attempted;
    readonly System.Windows.Forms.Timer clock=new System.Windows.Forms.Timer();
    string currentStep="准备就绪"; DateTime started;
    public InstallForm() {
        Text="攀岩助手 · 安装";
        float scale; using(var graphics=Graphics.FromHwnd(IntPtr.Zero)) scale=graphics.DpiX/96F;
        Func<int,int> px=value=>(int)Math.Ceiling(value*scale);
        AutoScaleMode=AutoScaleMode.None;
        ClientSize=new Size(px(520),px(340)); MinimumSize=SizeFromClientSize(ClientSize);
        StartPosition=FormStartPosition.CenterScreen; BackColor=Color.FromArgb(247,247,247);
        Font=new Font("Microsoft YaHei UI",9F); ForeColor=Color.FromArgb(32,32,32);
        var layout=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=1,RowCount=7,Padding=new Padding(px(30))};
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(50)));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(45)));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(32)));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(25)));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(25)));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(44)));
        var title=new Label {Text="攀岩助手",Font=new Font(Font.FontFamily,22F,FontStyle.Bold),Dock=DockStyle.Fill,AutoSize=false};
        var intro=new Label {Text="照片选线 · 视频复盘\n一次安装，之后直接打开使用。",Dock=DockStyle.Fill,ForeColor=Color.FromArgb(70,70,70)};
        step.Text="准备安装"; step.Font=new Font(Font.FontFamily,10F,FontStyle.Bold); step.Dock=DockStyle.Fill;
        progress.Dock=DockStyle.Top; progress.Height=px(8);
        detail.Text="首次需要联网\n安装约需 2.5 GB，完成后约 1.6 GB。";
        detail.Dock=DockStyle.Fill; detail.AutoSize=false;
        logs.Text="安装说明"; logs.AutoSize=true; logs.LinkColor=Color.FromArgb(70,70,70);
        logs.Click+=(s,e)=>{if(!attempted) MessageBox.Show(this,"自动准备环境和模型，无需配置 Python。\n空间为当前 Windows 环境实测并取整；缺少微软窗口组件时还需准备该组件。\n安装与重试保留个人资料。\n下载来源、许可和使用说明见 GitHub 项目 README。","安装说明"); else {Directory.CreateDirectory(WindowsApp.Cache);Process.Start("explorer.exe",WindowsApp.Quote(WindowsApp.Cache));}};
        main.Text="开始安装"; main.Width=px(140); main.Height=px(38); main.BackColor=Color.FromArgb(237,203,82);
        main.FlatStyle=FlatStyle.Flat; main.FlatAppearance.BorderSize=0; main.Anchor=AnchorStyles.Right;
        main.Click+=async(s,e)=>{if(completed) {Process.Start(app);Close();} else await StartInstall();};
        layout.Controls.Add(title);layout.Controls.Add(intro);layout.Controls.Add(step);
        layout.Controls.Add(progress);layout.Controls.Add(detail);layout.Controls.Add(logs);layout.Controls.Add(main);
        Controls.Add(layout); AcceptButton=main;
        clock.Interval=1000;clock.Tick+=(s,e)=>{if(running) {var elapsed=DateTime.Now-started;step.Text=currentStep+" · 已用 "+((int)elapsed.TotalMinutes)+" 分 "+elapsed.Seconds+" 秒";}};
        FormClosing+=(s,e)=>{if(running){e.Cancel=true;MessageBox.Show(this,"安装正在进行，请等待完成或显示失败后再关闭。","攀岩助手安装");}};
    }
    void UpdateLine(string line) {
        try {
            var item=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,object>>(line);
            BeginInvoke((Action)(()=>{
                currentStep=Convert.ToString(item["title"]);step.Text=currentStep; detail.Text=Convert.ToString(item["detail"]);logs.Text="查看日志";
                progress.Value=Math.Max(0,Math.Min(100,Convert.ToInt32(item["progress"])));
                if(item.ContainsKey("error")) {clock.Stop();main.Text="重试安装";}
                if(item.ContainsKey("done")) {app=Convert.ToString(item["app"]);completed=true;main.Text="打开攀岩助手";}
            }));
        } catch(Exception) { /* Raw process output belongs only in the log. */ }
    }
    async Task StartInstall() {
        running=true;completed=false;attempted=true;logs.Text="查看日志";main.Enabled=false;started=DateTime.Now;clock.Start();currentStep="准备安装资源（1/5）";step.Text=currentStep;detail.Text="正在展开程序文件，请稍候。";
        try {
            string payload=Path.Combine(WindowsApp.Cache,"payload");
            await Task.Run(()=>WindowsApp.Extract(payload));
            var info=new ProcessStartInfo(Path.Combine(payload,"runtime","python.exe"),
                WindowsApp.Quote(Path.Combine(payload,"installer","engine.py"))+" --payload "+WindowsApp.Quote(payload));
            info.WorkingDirectory=payload;info.UseShellExecute=false;info.CreateNoWindow=true;
            info.RedirectStandardOutput=true;info.RedirectStandardError=true;
            info.StandardOutputEncoding=Encoding.UTF8;info.StandardErrorEncoding=Encoding.UTF8;
            info.EnvironmentVariables.Remove("PYTHONHOME");info.EnvironmentVariables.Remove("PYTHONPATH");
            info.EnvironmentVariables["PYTHONUTF8"]="1";info.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
            using(var process=new Process()) {
                process.StartInfo=info;process.OutputDataReceived+=(s,e)=>{if(e.Data!=null) UpdateLine(e.Data);};
                process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null) {Directory.CreateDirectory(WindowsApp.Cache);File.AppendAllText(Path.Combine(WindowsApp.Cache,"安装日志.txt"),e.Data+Environment.NewLine,Encoding.UTF8);}};
                process.Start();process.BeginOutputReadLine();process.BeginErrorReadLine();
                await Task.Run(()=>process.WaitForExit());
                if(process.ExitCode!=0&&!completed) {main.Text="重试安装";}
            }
            if(completed) {
                // Only this installer's extracted resources; user data is elsewhere.
                string expected=Path.GetFullPath(WindowsApp.Cache)+Path.DirectorySeparatorChar;
                if(Path.GetFullPath(payload).StartsWith(expected,StringComparison.OrdinalIgnoreCase)) {
                    try {Directory.Delete(payload,true);} catch(IOException) {} catch(UnauthorizedAccessException) {}
                }
            }
        } catch(Exception) {step.Text="安装未完成";detail.Text="无法准备或启动安装资源。请检查磁盘空间后重试；若文件被安全软件隔离，请重新下载官方安装包并按系统提示处理。";main.Text="重试安装";}
        finally {running=false;clock.Stop();main.Enabled=true;}
    }
}
