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
using System.Collections.Generic;
using System.Runtime.InteropServices;

internal static class WindowsApp {
    internal const string Version = "0.1.17-local.20261010";
    internal static readonly string LocalRoot = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
    internal static readonly string ProgramRoot = Path.Combine(LocalRoot,"Programs","ClimbingAssistant");
    internal static readonly string Cache = Path.Combine(LocalRoot, "ClimbingSetup", "0.1.17");
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
            using(var mutex = new Mutex(true, "Local\\ClimbingAssistantSetup-" + Environment.UserName, out first)) {
                if(!first) { MessageBox.Show("另一个安装窗口已打开，请在那个窗口继续。", "攀岩助手安装"); return 1; }
                Application.Run(new InstallForm());
            }
            return 0;
        } catch(Exception) { MessageBox.Show("安装器启动失败。请检查磁盘空间，并重新下载官方安装包。", "攀岩助手安装", MessageBoxButtons.OK, MessageBoxIcon.Error); return 1; }
#endif
    }
    static int Launch() {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ClimbingAssistantSetup");
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
                info.EnvironmentVariables["LOCALAPPDATA"]=LocalRoot;
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

internal sealed class ProcessJob : IDisposable {
    [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
        public long ProcessTime,JobTime; public uint Flags;
        public UIntPtr MinWorking,MaxWorking; public uint ActiveLimit;
        public UIntPtr Affinity; public uint Priority,Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong A,B,C,D,E,F; }
    [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
        public BasicLimits Basic; public IoCounters Io;
        public UIntPtr ProcessMemory,JobMemory,PeakProcess,PeakJob;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr security,string name);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int kind,IntPtr data,uint length);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32.dll")] static extern bool TerminateJobObject(IntPtr job,uint code);
    [DllImport("kernel32.dll")] static extern bool QueryInformationJobObject(IntPtr job,int kind,IntPtr data,uint length,IntPtr returned);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    IntPtr handle;
    internal ProcessJob() {
        handle=CreateJobObject(IntPtr.Zero,null);
        if(handle==IntPtr.Zero) throw new IOException("Cannot create installation process job");
        var limits=new ExtendedLimits(); limits.Basic.Flags=0x2000; // KILL_ON_JOB_CLOSE
        int size=Marshal.SizeOf(limits); IntPtr data=Marshal.AllocHGlobal(size);
        try {
            Marshal.StructureToPtr(limits,data,false);
            if(!SetInformationJobObject(handle,9,data,(uint)size)) throw new IOException("Cannot configure installation job");
        } catch { CloseHandle(handle); handle=IntPtr.Zero; throw; }
        finally { Marshal.FreeHGlobal(data); }
    }
    internal void Assign(Process process) {
        if(!AssignProcessToJobObject(handle,process.Handle)) {
            process.Kill();process.WaitForExit();throw new IOException("Cannot isolate installation process");
        }
    }
    internal void Stop() { if(handle!=IntPtr.Zero && !TerminateJobObject(handle,2)) throw new IOException("Cannot stop installation process"); }
    internal void Drain() {
        IntPtr data=Marshal.AllocHGlobal(48);
        try {
            for(int attempt=0;attempt<150;attempt++) {
                if(!QueryInformationJobObject(handle,1,data,48,IntPtr.Zero)) throw new IOException("Cannot inspect installation processes");
                if(Marshal.ReadInt32(data,40)==0) return;
                Thread.Sleep(100);
            }
            throw new IOException("Installation processes are still running");
        } finally { Marshal.FreeHGlobal(data); }
    }
    public void Dispose() { if(handle!=IntPtr.Zero) {CloseHandle(handle);handle=IntPtr.Zero;} }
}

internal static class SetupCleanup {
    static Dictionary<string,object> Read(string file) { return new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(file,Encoding.UTF8)); }
    static void AssertTree(string path,string root) {
        string full=Path.GetFullPath(path),parent=Path.GetFullPath(root).TrimEnd('\\')+"\\";
        if(!full.StartsWith(parent,StringComparison.OrdinalIgnoreCase)) throw new IOException("Cleanup path outside installation root");
        if(!Directory.Exists(full)) return;
        // Reject junctions too, including a redirected ancestor.
        for(string current=full;current!=null;current=Path.GetDirectoryName(current))
            if(Directory.Exists(current) && (File.GetAttributes(current)&FileAttributes.ReparsePoint)!=0) throw new IOException("Redirected installation directory");
        foreach(string item in Directory.GetFileSystemEntries(full)) {
            if((File.GetAttributes(item)&FileAttributes.ReparsePoint)!=0) throw new IOException("Redirected installation file");
            if(Directory.Exists(item)) AssertTree(item,root);
        }
    }
    internal static void Clear(bool rollback) {
        string cache=WindowsApp.Cache,root=WindowsApp.ProgramRoot;
        string journal=Path.Combine(cache,"transaction.json");
        if(rollback && File.Exists(journal)) {
            var state=Read(journal);
            if(Convert.ToString(state["owner"])!="ClimbingAssistantSetup" ||
                Convert.ToString(state["version"])!=WindowsApp.Version ||
                !String.Equals(Path.GetFullPath(Convert.ToString(state["base"])),Path.GetFullPath(root),StringComparison.OrdinalIgnoreCase))
                throw new IOException("Installation ownership mismatch");
            string links=Path.Combine(cache,"links");
            if(File.Exists(Path.Combine(links,"links.json"))) {
                string script=Path.Combine(cache,"payload","installer","shortcuts.ps1");
                var info=new ProcessStartInfo("powershell.exe","-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "+
                    WindowsApp.Quote(script)+" -App "+WindowsApp.Quote(Path.Combine(root,WindowsApp.Version,"ClimbingAssistant.exe"))+
                    " -Directory "+WindowsApp.Quote(Path.Combine(root,WindowsApp.Version))+" -BackupDirectory "+WindowsApp.Quote(links)+" -Restore");
                info.UseShellExecute=false;info.CreateNoWindow=true;
                using(var process=Process.Start(info)) {
                    if(!process.WaitForExit(60000)) {process.Kill();process.WaitForExit();throw new IOException("Shortcut cleanup timed out");}
                    if(process.ExitCode!=0) throw new IOException("Cannot restore shortcuts");
                }
            }
            foreach(string name in new string[]{WindowsApp.Version+".installing",WindowsApp.Version}) {
                if(name==WindowsApp.Version && !Convert.ToBoolean(state["created_target"])) continue;
                string path=Path.Combine(root,name);
                if(!Directory.Exists(path)) continue;
                AssertTree(path,root);
                var marker=Read(Path.Combine(path,".setup-owned.json"));
                foreach(string key in new string[]{"owner","version","base","token","created_target"})
                    if(!marker.ContainsKey(key)||Convert.ToString(marker[key])!=Convert.ToString(state[key])) throw new IOException("Installation marker mismatch");
                string markerFile=Path.Combine(path,".setup-owned.json");
                foreach(string child in Directory.GetFileSystemEntries(path)) {
                    if(String.Equals(child,markerFile,StringComparison.OrdinalIgnoreCase)) continue;
                    if(Directory.Exists(child)) Directory.Delete(child,true); else File.Delete(child);
                }
                File.Delete(markerFile);Directory.Delete(path);
            }
        }
        if(Directory.Exists(cache)) {
            AssertTree(cache,Path.Combine(WindowsApp.LocalRoot,"ClimbingSetup"));
            Directory.Delete(cache,true);
        }
    }
    internal static void Retry(bool rollback) {
        for(int attempt=0;;attempt++) {
            try {Clear(rollback);return;}
            catch(IOException) {if(attempt>=9) throw;Thread.Sleep(300);}
            catch(UnauthorizedAccessException) {if(attempt>=9) throw;Thread.Sleep(300);}
        }
    }
}

internal sealed class InstallForm : Form {
    readonly Label step=new Label(),detail=new Label();
    readonly ProgressBar progress=new ProgressBar();
    readonly Button main=new Button(),stop=new Button(),cancel=new Button();
    readonly LinkLabel logs=new LinkLabel();
    readonly System.Windows.Forms.Timer clock=new System.Windows.Forms.Timer();
    readonly StringBuilder diagnostics=new StringBuilder();
    readonly object diagnosticGate=new object();
    string app,currentStep="准备安装",failureDetail;
    bool running,completed,attempted,cleanupPending,closeAfter,finishing;
    volatile bool stopRequested;
    ProcessJob job; DateTime started;
    public InstallForm() {
        Text="攀岩助手 · 安装";
        float scale;using(var graphics=Graphics.FromHwnd(IntPtr.Zero)) scale=graphics.DpiX/96F;
        Func<int,int> px=value=>(int)Math.Ceiling(value*scale);
        AutoScaleMode=AutoScaleMode.None;
        ClientSize=new Size(px(520),px(350));MinimumSize=SizeFromClientSize(ClientSize);
        StartPosition=FormStartPosition.CenterScreen;BackColor=Color.FromArgb(247,247,247);
        Font=new Font("Microsoft YaHei UI",9F);ForeColor=Color.FromArgb(32,32,32);
        var layout=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=1,RowCount=7,Padding=new Padding(px(30))};
        foreach(int height in new[]{50,45,32,25}) layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(height)));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(25)));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,px(44)));
        var title=new Label {Text="攀岩助手",Font=new Font(Font.FontFamily,22F,FontStyle.Bold),Dock=DockStyle.Fill};
        var intro=new Label {Text="照片选线 · 视频复盘\n一次安装，之后直接打开使用。",Dock=DockStyle.Fill,ForeColor=Color.FromArgb(70,70,70)};
        step.Text=currentStep;step.Font=new Font(Font.FontFamily,10F,FontStyle.Bold);step.Dock=DockStyle.Fill;
        progress.Dock=DockStyle.Top;progress.Height=px(8);
        detail.Text="首次需要联网\n安装约需 2.5 GB，完成后约 1.6 GB。";detail.Dock=DockStyle.Fill;
        logs.Text="安装说明";logs.AutoSize=true;logs.LinkColor=Color.FromArgb(70,70,70);
        logs.Click+=(s,e)=>{
            if(!attempted) MessageBox.Show(this,"自动准备环境和模型，无需配置 Python。\n失败、停止或取消会清理本次安装文件，保留已有应用和个人资料。\n空间为本机实测并取整；缺少微软窗口组件时需另准备该共享组件。\n下载来源和许可见 GitHub 项目 README。","安装说明");
            else ShowLog();
        };
        main.Text="开始安装";main.Width=px(140);main.Height=px(38);main.BackColor=Color.FromArgb(237,203,82);
        main.FlatStyle=FlatStyle.Flat;main.FlatAppearance.BorderSize=0;main.Anchor=AnchorStyles.Right;
        main.Click+=async(s,e)=>{if(cleanupPending) await FinishCleanup(); else if(completed) {Process.Start(app);Close();} else await StartInstall();};
        foreach(var button in new[]{stop,cancel}) {
            button.Width=px(90);button.Height=px(38);button.FlatStyle=FlatStyle.Flat;
            button.FlatAppearance.BorderSize=0;button.BackColor=BackColor;button.Anchor=AnchorStyles.Left;
        }
        stop.Text="停止安装";stop.Enabled=false;cancel.Text="取消安装";
        stop.Click+=(s,e)=>RequestStop(false);
        cancel.Click+=async(s,e)=>{if(running) RequestStop(true);else if(cleanupPending){closeAfter=true;await FinishCleanup();}else Close();};
        var actions=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=4,RowCount=1,Margin=Padding.Empty};
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,px(95)));actions.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,px(95)));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));actions.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,px(140)));
        actions.Controls.Add(stop,0,0);actions.Controls.Add(cancel,1,0);actions.Controls.Add(main,3,0);
        layout.Controls.Add(title);layout.Controls.Add(intro);layout.Controls.Add(step);layout.Controls.Add(progress);
        layout.Controls.Add(detail);layout.Controls.Add(logs);layout.Controls.Add(actions);Controls.Add(layout);AcceptButton=main;
        clock.Interval=1000;clock.Tick+=(s,e)=>{if(running&&!stopRequested) {var elapsed=DateTime.Now-started;step.Text=currentStep+" · 已用 "+((int)elapsed.TotalMinutes)+" 分 "+elapsed.Seconds+" 秒";}};
        FormClosing+=(s,e)=>{if(running){e.Cancel=true;RequestStop(true);}else if(cleanupPending){e.Cancel=true;closeAfter=true;main.PerformClick();}};
    }
    void Record(string text) {lock(diagnosticGate) {diagnostics.AppendLine(text);if(diagnostics.Length>500000) diagnostics.Remove(0,diagnostics.Length-500000);}}
    void ShowLog() {
        using(var dialog=new Form {Text="安装日志",Size=new Size(760,480),StartPosition=FormStartPosition.CenterParent}) {
            var text=new TextBox {Multiline=true,ReadOnly=true,Dock=DockStyle.Fill,ScrollBars=ScrollBars.Both,WordWrap=false};
            lock(diagnosticGate) text.Text=diagnostics.ToString();
            if(text.Text.Length==0) text.Text="尚无错误记录。";
            dialog.Controls.Add(text);dialog.ShowDialog(this);
        }
    }
    void RequestStop(bool exit) {
        if(!running) return;
        if(finishing) {closeAfter|=exit;return;}
        closeAfter|=exit;stopRequested=true;stop.Enabled=false;cancel.Enabled=false;clock.Stop();
        step.Text="正在停止并清理";detail.Text="请稍候，正在清理本次安装文件。";
        if(job!=null) try {job.Stop();} catch(Exception ex){Record(ex.ToString());}
    }
    void UpdateLine(string line) {
        try {
            var item=new JavaScriptSerializer {MaxJsonLength=2000000}.Deserialize<Dictionary<string,object>>(line);
            if(item.ContainsKey("log")) Record(Convert.ToString(item["log"]));
            BeginInvoke((Action)(()=>{
                if(stopRequested) return;
                currentStep=Convert.ToString(item["title"]);step.Text=currentStep;detail.Text=Convert.ToString(item["detail"]);
                progress.Value=Math.Max(0,Math.Min(100,Convert.ToInt32(item["progress"])));
                if(item.ContainsKey("error")) failureDetail=Convert.ToString(item["detail"]);
                if(item.ContainsKey("done")) app=Convert.ToString(item["app"]);
            }));
        } catch(Exception){Record(line);}
    }
    async Task FinishCleanup() {
        main.Enabled=false;cancel.Enabled=false;step.Text="正在清理";detail.Text="正在清理本次安装文件，请稍候。";
        try {
            await Task.Run(()=>SetupCleanup.Retry(!completed));
            cleanupPending=false;step.Text=completed?"安装完成":"安装已停止";
            detail.Text=completed?"可直接打开使用。":"本次安装文件已清理。";
            main.Text=completed?"打开攀岩助手":"重新安装";
            if(closeAfter) Close();
        } catch(Exception ex) {Record(ex.ToString());step.Text="清理未完成";detail.Text="文件仍被占用，请关闭占用程序后点击「继续清理」。";main.Text="继续清理";}
        finally {main.Enabled=true;cancel.Enabled=true;}
    }
    async Task StartInstall() {
        running=true;completed=false;attempted=true;stopRequested=false;closeAfter=false;finishing=false;app=null;failureDetail=null;
        lock(diagnosticGate) diagnostics.Clear();
        logs.Text="查看日志";main.Enabled=false;stop.Enabled=true;cancel.Enabled=true;
        started=DateTime.Now;clock.Start();currentStep="准备安装资源（1/5）";step.Text=currentStep;detail.Text="正在展开程序文件，请稍候。";
        bool success=false,drained=true;
        try {
            // Recover an interrupted prior attempt before replacing its ownership journal.
            await Task.Run(()=>SetupCleanup.Retry(true));
            string payload=Path.Combine(WindowsApp.Cache,"payload");
            await Task.Run(()=>WindowsApp.Extract(payload));
            if(!stopRequested) {
                string gateName="Local\\ClimbingAssistantGate-"+Guid.NewGuid().ToString("N");
                using(var startGate=new EventWaitHandle(false,EventResetMode.ManualReset,gateName))
                using(var owned=new ProcessJob())
                using(var process=new Process()) {
                    job=owned;
                    var info=new ProcessStartInfo(Path.Combine(payload,"runtime","python.exe"),
                        WindowsApp.Quote(Path.Combine(payload,"installer","engine.py"))+" --payload "+WindowsApp.Quote(payload)+
                        " --base "+WindowsApp.Quote(WindowsApp.ProgramRoot)+" --cache "+WindowsApp.Quote(WindowsApp.Cache)+" --gate "+WindowsApp.Quote(gateName));
                    info.WorkingDirectory=payload;info.UseShellExecute=false;info.CreateNoWindow=true;
                    info.RedirectStandardOutput=true;info.RedirectStandardError=true;
                    info.StandardOutputEncoding=Encoding.UTF8;info.StandardErrorEncoding=Encoding.UTF8;
                    foreach(string key in new[]{"PYTHONHOME","PYTHONPATH","VIRTUAL_ENV"}) info.EnvironmentVariables.Remove(key);
                    info.EnvironmentVariables["LOCALAPPDATA"]=WindowsApp.LocalRoot;
                    info.EnvironmentVariables["PYTHONUTF8"]="1";info.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
                    process.StartInfo=info;process.OutputDataReceived+=(s,e)=>{if(e.Data!=null) UpdateLine(e.Data);};
                    process.ErrorDataReceived+=(s,e)=>{if(e.Data!=null) Record(e.Data);};
                    process.Start();owned.Assign(process);startGate.Set();process.BeginOutputReadLine();process.BeginErrorReadLine();
                    await Task.Run(()=>process.WaitForExit());
                    success=process.ExitCode==0&&!stopRequested;
                    if(!success) owned.Stop();
                    try {await Task.Run(()=>owned.Drain());} catch {drained=false;throw;}
                    job=null;
                }
            }
        } catch(Exception ex) {Record(ex.ToString());failureDetail="无法完成安装，请查看日志后重新安装。";}
        {
            // Commit the result on the UI thread after processing any stop request
            // received while the engine/children were exiting. Cleanup is atomic:
            // once the app is fully installed, closing only waits for cache cleanup.
            success=success&&!stopRequested;finishing=true;stop.Enabled=false;cancel.Enabled=false;
            job=null;clock.Stop();
            if(!drained) {cleanupPending=true;success=false;}
            else {
                step.Text="正在清理";detail.Text="正在清理本次安装临时文件。";
                try {await Task.Run(()=>SetupCleanup.Retry(!success));cleanupPending=false;}
                catch(Exception ex){Record(ex.ToString());cleanupPending=true;}
            }
            running=false;finishing=false;completed=success;
            stop.Enabled=false;main.Enabled=true;cancel.Enabled=true;progress.Value=success?100:0;
            cancel.Text=completed?"关闭":"取消安装";
            if(cleanupPending) {step.Text="清理未完成";detail.Text="文件仍被占用，请关闭占用程序后点击「继续清理」。";main.Text="继续清理";}
            else if(success) {step.Text="安装完成";detail.Text="可直接打开使用。";main.Text="打开攀岩助手";}
            else {step.Text=stopRequested?"安装已停止":"安装未完成";detail.Text=stopRequested?"本次安装文件已清理。":(failureDetail??"请查看日志后重新安装。").Replace(" 本次安装文件已清理。","").Replace(" 清理未完成，请点击取消安装继续清理。","")+"\n本次安装文件已清理。";main.Text="重新安装";}
            if(closeAfter&&!cleanupPending) Close();
        }
    }
}
