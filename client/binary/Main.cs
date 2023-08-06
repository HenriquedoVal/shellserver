using System;
using System.IO;
using System.Threading;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;

using System.Management.Automation;
using System.Management.Automation.Language;
using System.Management.Automation.Runspaces;
using System.Management.Automation.Subsystem;
using System.Management.Automation.Subsystem.Prediction;

using Microsoft.Win32;
using Microsoft.PowerShell.Commands;


namespace ShellServer
{
    public class Globals : IModuleAssemblyInitializer, IModuleAssemblyCleanup
    {
        public static UdpClient client = new UdpClient();
        public static Hashtable lightColors;
        public static Hashtable darkColors;
        public static string[] pathCmdCompletions;
        public static bool isLight;

        const short port = 5432;

        static IPEndPoint endpoint = new IPEndPoint(
                IPAddress.Loopback, port
        );
        static UTF8Encoding encoder = new UTF8Encoding();

        private const string predictorIdentifier = "ce865750-f55b-4bf6-a302-fcba803b1442";

        public void OnImport()
        {
            client.Connect("localhost", port);
            SendToServer("2InitpwshBin");

            Runspace.DefaultRunspace.Events.SubscribeEvent(
                 null, null, PSEngineEvent.Exiting, null,
                 new PSEventReceivedEventHandler(ExitHandler),
                 false, false
            );
        }

        public void OnRemove(PSModuleInfo psModuleInfo)
        {
            SubsystemManager.UnregisterSubsystem(
                    SubsystemKind.CommandPredictor, new Guid(predictorIdentifier)
            );
        }

        public static void ThreadInit()
        {
            Helpers.UpdateCompletions();

            const string readlineAsm = "Microsoft.PowerShell.PSReadLine";
            var currAsms = AppDomain.CurrentDomain.GetAssemblies();
           
            foreach (Assembly asm in currAsms)
            {
                if (asm.FullName.StartsWith(readlineAsm))
                {
                    var types = asm.GetExportedTypes();
                    foreach (Type t in types)
                    {
                        if (t.Name == "PSConsoleReadLine")
                        {
                            ReadLine.ReadLineClass = t;
                            break;
                        }
                    }
                    break;
                }
            }

            // Serialize???
            var colors = new Hashtable();

            colors["Command"]                = "\x1b[93m"    ;
            colors["Comment"]                = "\x1b[92m"    ;
            colors["ContinuationPrompt"]     = "\x1b[94m"    ;
            colors["DefaultToken"]           = "\x1b[97m"    ;
            colors["Emphasis"]               = "\x1b[96m"    ;
            colors["InlinePrediction"]       = "\x1b[90m"    ;
            colors["Keyword"]                = "\x1b[92m"    ;
            colors["ListPrediction"]         = "\x1b[33m"    ;
            colors["ListPredictionSelected"] = "\x1b[34;238m";
            colors["Member"]                 = "\x1b[34m"    ;
            colors["Number"]                 = "\x1b[34m"    ;
            colors["Operator"]               = "DarkGray"    ;
            colors["Parameter"]              = "DarkGray"    ;
            colors["Selection"]              = "\x1b[34;238m";
            colors["String"]                 = "DarkCyan"    ;
            colors["Type"]                   = "\x1b[32m"    ;
            colors["Variable"]               = "Green"       ;

            lightColors = (Hashtable)colors.Clone();

            colors["Command"]                = "\x1b[93m"      ;
            colors["Comment"]                = "\x1b[32m"      ;
            colors["ContinuationPrompt"]     = "\x1b[34m"      ;
            colors["DefaultToken"]           = "\x1b[37m"      ;
            colors["Emphasis"]               = "\x1b[96m"      ;
            colors["InlinePrediction"]       = "\x1b[38;5;238m";
            colors["Keyword"]                = "\x1b[92m"      ;
            colors["ListPrediction"]         = "\x1b[33m"      ;
            colors["ListPredictionSelected"] = "\x1b[48;5;238m";
            colors["Member"]                 = "\x1b[97m"      ;
            colors["Number"]                 = "\x1b[97m"      ;
            colors["Operator"]               = "\x1b[90m"      ;
            colors["Parameter"]              = "\x1b[90m"      ;
            colors["Selection"]              = "\x1b[30;47m"   ;
            colors["String"]                 = "\x1b[36m"      ;
            colors["Type"]                   = "\x1b[34m"      ;
            colors["Variable"]               = "\x1b[92m"      ;

            darkColors = colors;

            const string subKey = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize";

            using (var key = Registry.CurrentUser.OpenSubKey(subKey, false))
            {
                var value = key?.GetValue("SystemUsesLightTheme");
                if ((int)value == 1) isLight = true;
            }

            if (isLight) ReadLine.SetReadLineTheme(ref lightColors);

            var handler = new object[4];

            handler[0] = new string[] {"Enter"};
            handler[1] = ScriptBlock.Create("Invoke-ShellServerEnterKeyHandler");
            handler[2] = "ShellServer Module Enter key handler";
            handler[3] = "";

            ReadLine.Invoke(
                    ReadLine.SetKeyHandler,
                    ref handler
            );

            client.Client.ReceiveTimeout = 3000;

            var predictor = new ShellServerFuzzyPredictor(predictorIdentifier);
            SubsystemManager.RegisterSubsystem(SubsystemKind.CommandPredictor, predictor);
        }

        static void ExitHandler(object sender, EventArgs e)
        {
            try
            {
                SendToServer("2Exit");
            }
            catch (Exception) {}

        }

        public static void SendToServer(string msg)
        {
            byte[] buffer = encoder.GetBytes(msg);
            client.Send(buffer, buffer.Length);
        }

        public static string ReceiveFromServer()
        {
            byte[] response;
            string responseString;
            char initialChar;
            string msg = "";

            while (true)
            {
                response = Globals.client.Receive(
                        ref Globals.endpoint
                );
                responseString = Globals.encoder.GetString(
                        response, 0, response.Length
                );
                initialChar = responseString[0];
                msg += responseString.Substring(1);
                if (initialChar == '0') break;
            }

            return msg;
        }
    }

    class ReadLine
    // Just CAN'T reference Microsoft.PowerShell.PSConsoleReadLine in compilation time.
    {
        public const string ValidateAndAcceptLine = "ValidateAndAcceptLine";
        public const string GetBufferState = "GetBufferState";
        public const string SetKeyHandler = "SetKeyHandler";
        public const string GetOptions = "GetOptions";
        // public const string SetOptions = "SetOptions";

        public static Type ReadLineClass;

        public static object[] GetBufferStateArgs = new object[4];
        public static object[] ValidateAndAcceptLineArgs = {null, null};

        public static object? Invoke(string methodName, ref object[] args)
        {
            return ReadLineClass.InvokeMember(
                    methodName,
                    BindingFlags.InvokeMethod,
                    Type.DefaultBinder,
                    null,
                    args
            );
        }

        public static void SetReadLineTheme(ref Hashtable colors)
        {
            var arg = Array.Empty<object>();
            var inst = ReadLine.Invoke(
                    ReadLine.GetOptions,
                    ref arg
            );

            foreach (DictionaryEntry entry in colors)
            {
                inst.GetType().InvokeMember(
                    entry.Key.ToString() + "Color",
                    BindingFlags.Public | BindingFlags.SetProperty | BindingFlags.Instance,
                    Type.DefaultBinder,
                    inst,
                    new object[] {entry.Value.ToString()}
                );
            }
        }
    }

    class Helpers
    // Support for cmdlets, not needed on startup.
    {
        public static void UpdateCompletions()
        {
            Globals.SendToServer("2Get");
            string completions = Globals.ReceiveFromServer();
            Globals.pathCmdCompletions = completions.Split(';');

            Globals.SendToServer("4Get");
            
            ShellServerFuzzyPredictor.container.Clear();

            string response = Globals.ReceiveFromServer();
            string[] paths = response.Split('\n');

            foreach (string fullPath in paths)
            {
                string lastPath = fullPath.Substring(
                        fullPath.LastIndexOf('\\') + 1
                );
            
                if (lastPath.Length == 0) lastPath = fullPath;
            
                ShellServerFuzzyPredictor.container.Add(
                        (20, Tuple.Create(lastPath, fullPath))
                );
            }
        }

        public static string ServerListDir(
                string path, string curdir, string opt
        )
        {
            string target;

            if (path is null) target = curdir;
            else target = Path.Combine(curdir, path);
            
            string msg = $"5{opt};{target}";

            Globals.SendToServer(msg);
            return Globals.ReceiveFromServer();
        }
    }

    class SeverRefPathsAndDirsCompleter: IArgumentCompleter
    {
        DirsCompleter Dirs = new DirsCompleter();
        ServerPathRefsCompleter ServerRefs = new ServerPathRefsCompleter();

        public IEnumerable<CompletionResult> CompleteArgument(
            string commandName,
            string parameterName,
            string wordToComplete,
            CommandAst commandAst,
            System.Collections.IDictionary fakeBoundParameters
        )
        {
            foreach (CompletionResult comp in ServerRefs.CompleteArgument(
                        commandName, parameterName, wordToComplete, commandAst, fakeBoundParameters)
            )
            {
                yield return comp;
            }

            foreach (CompletionResult comp in Dirs.CompleteArgument(
                        commandName, parameterName, wordToComplete, commandAst, fakeBoundParameters)
            )
            {
                yield return comp;
            }
        }
    }

    class ServerPathRefsCompleter: IArgumentCompleter
    {
         public IEnumerable<CompletionResult> CompleteArgument(
            string commandName,
            string parameterName,
            string wordToComplete,
            CommandAst commandAst,
            System.Collections.IDictionary fakeBoundParameters
        )
        {
            // Refer directly Globals so it can dinamically change
            foreach (string comp in Globals.pathCmdCompletions)
            {
                if (
                        string.IsNullOrEmpty(wordToComplete)
                        || comp.StartsWith(wordToComplete)
                )
                {
                    string res = comp;
                    if (comp.Contains(' ')) res = $@"""{comp}""";
                    yield return new CompletionResult(
                            res, res,
                            CompletionResultType.ParameterValue,
                            "ShellServer path reference"
                    );
                }
            }
        }
    }

    class DirsCompleter: IArgumentCompleter
    {
        public IEnumerable<CompletionResult> CompleteArgument(
            string commandName,
            string parameterName,
            string wordToComplete,
            CommandAst commandAst,
            System.Collections.IDictionary fakeBoundParameters
        )
        {
            var pathCompletions = CompletionCompleters.CompleteFilename(wordToComplete);
            foreach (var res in pathCompletions)
            {
                // ToolTip is the abs path.
                var attr = File.GetAttributes(res.ToolTip);
                bool isDir = (attr & FileAttributes.Directory) > 0;
                
                if (isDir) yield return res;
            }
        }
    }

    class NoneCompleter: IArgumentCompleter
    {
        public IEnumerable<CompletionResult> CompleteArgument(
            string commandName,
            string parameterName,
            string wordToComplete,
            CommandAst commandAst,
            System.Collections.IDictionary fakeBoundParameters
        ) => default;
    }

    public class ShellServerFuzzyPredictor : ICommandPredictor
    {
        // List<(distance, (pathRef, fullPath))>
        public static List<ValueTuple<int, Tuple<string, string>>> container =
            new List<ValueTuple<int, Tuple<string, string>>>();

        readonly List<string> cmds = new List<string> {"pz", "set-shellserverpathfuzzy"};

        private object _optionsInst;
        private object _userStyle;
        private PropertyInfo _predictionSourceProperty;

        private readonly Guid _guid;

        internal ShellServerFuzzyPredictor(string guid)
        {
            _guid = new Guid(guid);

            var arg = Array.Empty<object>();
            _optionsInst = ReadLine.Invoke(
                    ReadLine.GetOptions,
                    ref arg
            ) ;
            _predictionSourceProperty = _optionsInst.GetType().GetProperty("PredictionSource");

            _userStyle = _predictionSourceProperty.GetValue(
                    _optionsInst
            );
        }

        public Guid Id => _guid;

        public string Name => "ShellServer";

        public string Description => "Provides prediction for the `Set-ShellServerPathFuzzy` Cmdlet.";

        static int GetDamerauLevenshteinDistance(string s, string t)
        // Totally stolen from https://www.csharpstar.com/csharp-string-distance-algorithm/
        {
            var bounds = new { Height = s.Length + 1, Width = t.Length + 1 };

            int[,] matrix = new int[bounds.Height, bounds.Width];

            for (int height = 0; height < bounds.Height; height++) { matrix[height, 0] = height; };
            for (int width = 0; width < bounds.Width; width++) { matrix[0, width] = width; };

            for (int height = 1; height < bounds.Height; height++)
            {
                for (int width = 1; width < bounds.Width; width++)
                {
                    int cost = (s[height - 1] == t[width - 1]) ? 0 : 1;
                    int insertion = matrix[height, width - 1] + 1;
                    int deletion = matrix[height - 1, width] + 1;
                    int substitution = matrix[height - 1, width - 1] + cost;

                    int distance = Math.Min(insertion, Math.Min(deletion, substitution));

                    if (height > 1 && width > 1 && s[height - 1] == t[width - 2] && s[height - 2] == t[width - 1])
                    {
                        distance = Math.Min(distance, matrix[height - 2, width - 2] + cost);
                    }

                    matrix[height, width] = distance;
                }
            }

            return matrix[bounds.Height - 1, bounds.Width - 1];
        }

        public static void SortContainer(string args)
        {
            bool caseSensitive = args != args.ToLower();
            string refPath;

            for (int i = 0; i < container.Count; i++)
            {
                refPath = container[i].Item2.Item1;

                if (!caseSensitive) refPath = refPath.ToLower();

                int dld = GetDamerauLevenshteinDistance(args, refPath);
                container[i] = (dld, container[i].Item2);
            }

            container.Sort();
        }

        public SuggestionPackage GetSuggestion(
            PredictionClient client, PredictionContext context, CancellationToken cancellationToken
        )
        {
            string input = context.InputAst.Extent.Text;
            if (string.IsNullOrWhiteSpace(input))
            {
                return default;
            }

            var tokens = context.InputTokens;
            var cmd = tokens[0];

            if (
                    (cmd.TokenFlags != TokenFlags.CommandName)
                    || (!cmds.Contains(cmd.Text.ToLower()))
                    
                    // In the input "pz arg" there are 3 tokens:
                    // `pz`, `arg` and `endOfInput`
                    || (tokens.Count < 3) 
            )
            {
                return default;
            }

            // Set PredictionSource to `Plugin` only.
            this._predictionSourceProperty.SetValue(
                    this._optionsInst, 4
            );

            // If there are 3 tokens, there is a space and something more
            string args = input.Substring(input.IndexOf(' ') + 1);
            SortContainer(args);

            int threshold = container[0].Item1 + 2;

            var res = new List<PredictiveSuggestion>();

            for (int i = 0; i < container.Count; i++)
            {
                var target = container[i];
                if (target.Item1 <= threshold)
                {
                    string fullPath = target.Item2.Item2;

                    if (fullPath.Contains(' ')) fullPath = @$"""{fullPath}""";

                    res.Add(new PredictiveSuggestion(
                        string.Concat(input, " " + fullPath))
                    );
                }
            }

            return new SuggestionPackage(res);
        }

        public bool CanAcceptFeedback(PredictionClient client, PredictorFeedbackKind feedback)
        {
            if (feedback == PredictorFeedbackKind.CommandLineExecuted)
            {
                return true;
            }
            return false;
        }

        public void OnSuggestionDisplayed(PredictionClient client, uint session, int countOrIndex) { }

        public void OnSuggestionAccepted(PredictionClient client, uint session, string acceptedSuggestion) { }

        public void OnCommandLineAccepted(PredictionClient client, IReadOnlyList<string> history) { }

        public void OnCommandLineExecuted(PredictionClient client, string commandLine, bool success)
        {
            this._predictionSourceProperty.SetValue(
                    this._optionsInst, this._userStyle
            );
        }
    }

    [Cmdlet(VerbsLifecycle.Invoke, "ShellServerPrompt")]
    [Alias("prompt")]
    [OutputType(typeof(void))]
    public class PromptCmd : PSCmdlet
    {
        static readonly string admin =
            IsUserAnAdmin() ? "(Admin) " : "";
        
        static bool firstPrompt = true;

        [DllImport("shell32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool IsUserAnAdmin();

        protected override void ProcessRecord()
        {
            int width = Host.UI.RawUI.BufferSize.Width;
            string venv = Environment.GetEnvironmentVariable("VIRTUAL_ENV");
            string path = SessionState.Path.CurrentLocation.Path;
            var question = Convert.ToInt16(GetVariableValue("?"));

            var res = SessionState.InvokeCommand.InvokeScript(
                    "Get-History -Count 1"
            );

            double duration;

            if (res.Count > 0 && res[0] != null)
            {
                var hist = res[0].ImmediateBaseObject as HistoryInfo;
                duration = (hist.EndExecutionTime - hist.StartExecutionTime)
                        .TotalSeconds;
            }
            else
            {
                duration = 0.0;
            }

            if (venv != null)
            {
                venv = venv.Substring(
                        venv.LastIndexOf('\\') + 1);
                venv = $"({venv}) ";

                width -= venv.Length;
            }
            else
            {
                venv = "";
            }

            width -= admin.Length;

            Globals.SendToServer($"1{question}{path};{width};{duration}");

            string prompt;

            try
            {
                prompt = Globals.ReceiveFromServer();
            }
            catch (SocketException e)
            {
                string msg = "Server didn't respond in time. Press Enter to return to previous prompt.";
                Console.WriteLine(msg);
               
                WriteError(
                    new ErrorRecord(
                        e,
                        "Server didn't respond in time.",
                        ErrorCategory.OperationTimeout,
                        null
                    )
                );

                SessionState.InvokeCommand.InvokeScript(
                        "Remove-Alias -Name prompt"
                );
                SessionState.InvokeCommand.InvokeScript(
                        "Set-PSReadLineKeyHandler -Key Enter -Function AcceptLine"
                );
                return;
            }

            if (firstPrompt)
            {
                new Thread(new ThreadStart(Globals.ThreadInit)).Start();
                firstPrompt = false;
            }

            char changed = prompt[0];
            prompt = prompt.Substring(1);

            if (changed == '1')
            {
                // It's the server responsability to not send `changed` in the first prompt
                new Thread(new ThreadStart(Helpers.UpdateCompletions)).Start();
            }

            WriteObject($"\n\x1b[31m{admin}\x1b[32m{venv}{prompt}");
        }
    }
    
    [Cmdlet(VerbsCommon.Set, "ShellServerPath")]
    [Alias("p")]
    [OutputType(typeof(void))]
    public class PathCmd : PSCmdlet
    {
        static readonly string HOME =
            Environment.GetEnvironmentVariable("USERPROFILE");

        // Had to make a choice here, specific completers
        // or the ease of use of `SwitchParameter`

        [Parameter()]
        [Alias("D")]
        [ArgumentCompleter(typeof(DirsCompleter))]
        public string Delete {get; set;}

        [Parameter()]
        [Alias("DR")]
        [ArgumentCompleter(typeof(ServerPathRefsCompleter))]
        public string DeletePathRef {get; set;}

        [Parameter()]
        [Alias("A")]
        [ArgumentCompleter(typeof(DirsCompleter))]
        public string Add {get; set;}

        [Parameter()]
        [ArgumentCompleter(typeof(NoneCompleter))]
        public string As {get; set;}

        [Parameter()]
        [Alias("O")]
        public SwitchParameter Output {get; set;}

        [Parameter()]
        [Alias("J")]
        public SwitchParameter Junction {get; set;}

        [Parameter(Position = 0)]
        [ArgumentCompleter(typeof(SeverRefPathsAndDirsCompleter))]
        public string PathOrPathRef;

        // resolution order:
        // p -d . -dr someref -a . -as anyname anyref -j -o

        string? ResolveJunction(string path)
        {
            var attr = File.GetAttributes(path);

            bool isDir = (attr & FileAttributes.Directory) > 0;
            bool isJunction = (attr & FileAttributes.ReparsePoint) > 0;

            if (!(isDir && isJunction))
            {
                WriteError(
                    new ErrorRecord(
                        new ArgumentException($"Junction for '{path}' not found."),
                        "A directory junction for the given path was not found.",
                        ErrorCategory.ObjectNotFound,
                        null
                    )
                );
                return null;
            }

            return Directory.ResolveLinkTarget(path, false).FullName;
        }

        string? ResolveArg(string arg, string curdir)
        {
            // GetFullPath will resolve . and ..
            arg = Path.GetFullPath(Path.Combine(curdir, arg)).TrimEnd('\\');

            if (!Path.Exists(arg))
            {
                WriteError(
                    new ErrorRecord(
                        new ArgumentException($"'{arg}' not found."),
                        "No existing relative or full paths matches arg.",
                        ErrorCategory.ObjectNotFound,
                        null
                    )
                );
                return null;
            }

            var attr = File.GetAttributes(arg);
            bool isDir = (attr & FileAttributes.Directory) > 0;

            if (!isDir)
            {
                WriteError(
                    new ErrorRecord(
                        new ArgumentException($"'{arg}' is not a directory."),
                        "Paths to this command must be directories.",
                        ErrorCategory.InvalidArgument,
                        null
                    )
                );
                return null;
            }

            return arg;
        }

        protected override void ProcessRecord()
        {
            bool anyBeforeWasUsed = false;
            string curdir = SessionState.Path.CurrentLocation.Path;
            string target;

            if (!string.IsNullOrEmpty(Delete))
            {
                anyBeforeWasUsed = true;
                target = ResolveArg(Delete, curdir);
                if (target != null)
                    Globals.SendToServer($"9Del{target}");
            }

            if (!string.IsNullOrEmpty(DeletePathRef))
            {
                anyBeforeWasUsed = true;
                Globals.SendToServer($"9DRf{DeletePathRef}");;
            }

            if (!string.IsNullOrEmpty(Add))
            {
                anyBeforeWasUsed = true;
                target = ResolveArg(Add, curdir);
                if (target != null)
                    Globals.SendToServer($"9Add{target};{As}");
            }

            if (
                    string.IsNullOrEmpty(PathOrPathRef)
                    && !Junction.IsPresent
                    && !Output.IsPresent
                    && anyBeforeWasUsed
            )
            {
                return;
            }

            if (!string.IsNullOrEmpty(PathOrPathRef))
            {
                // Sever will return empty string for `.\pathref\`
                // but returns for `pathref` if it exists
                // so purpose is clear when user pass rel-path-like
                Globals.SendToServer($"3{PathOrPathRef}");
                target = Globals.ReceiveFromServer();

                if (string.IsNullOrEmpty(target))
                {
                    if (Path.IsPathFullyQualified(PathOrPathRef))
                        target = PathOrPathRef;
                    else
                        target = ResolveArg(PathOrPathRef, curdir);

                    if (target is null) return;
                }
            }
            else
            {
                target = Junction.IsPresent ? curdir : HOME;
            }

            if (Junction.IsPresent)
            {
                target = ResolveJunction(target);
                if (target is null) return;
            }

            if (Output.IsPresent)
            {
                WriteObject(target);
                return;
            }

            SessionState.Path.SetLocation(target);
        }
    }

    [Cmdlet(VerbsCommon.Set, "ShellServerPathFuzzy")]
    [Alias("pz")]
    [OutputType(typeof(void))]
    public class PathFuzzyCmd : PSCmdlet
    {
        [Parameter(
                ValueFromRemainingArguments = true,
                Mandatory = true,
                Position = 0
        )]
        [ArgumentCompleter(typeof(NoneCompleter))]
        public string[] Query;

        protected override void ProcessRecord()
        {
            string chosenPath;
            string lastArg = Query[Query.Length - 1];

            if (Path.IsPathFullyQualified(lastArg))
            {
                chosenPath = lastArg;
            }
            else if (ShellServerFuzzyPredictor.container.Count > 0)
            {
                string args = string.Join(' ', Query);
                ShellServerFuzzyPredictor.SortContainer(args);
                chosenPath =
                    ShellServerFuzzyPredictor.container[0].Item2.Item2;
            }
            else
            {
                WriteObject("The cache is empty.");
                return;
            }

            SessionState.Path.SetLocation(chosenPath);
            Globals.SendToServer($"4{chosenPath}");
            chosenPath = null;
        }
    }

    [Cmdlet(VerbsCommon.Get, "ShellServerListDir")]
    [Alias("ll")]
    [OutputType(typeof(string))]
    public class ListDirCmd : PSCmdlet
    {
        [Parameter()]
        [Alias("A")]
        public SwitchParameter All;

        [Parameter()]
        [Alias("C")]
        public SwitchParameter Color;

        [Parameter()]
        [Alias("I")]
        public SwitchParameter Icons;

        [Parameter()]
        [Alias("L")]
        public SwitchParameter List;

        [Parameter()]
        [Alias("CR")]
        public SwitchParameter CreationTime;

        [Parameter()]
        [Alias("M")]
        public SwitchParameter ModifiedTime;

        [Parameter()]
        [Alias("AC")]
        public SwitchParameter AccessTime;

        [Parameter()]
        [Alias("H")]
        public SwitchParameter Hour;

        [Parameter()]
        [Alias("HE")]
        public SwitchParameter Headers;

        [Parameter()]
        public SwitchParameter SetDefault;

        [Parameter()]
        public SwitchParameter NoOutput;

        [Parameter(Position = 0)]
        [ArgumentCompleter(typeof(DirsCompleter))]
        public string Path { get; set; }

        [Parameter()]
        [ArgumentCompleter(typeof(NoneCompleter))]
        public string Options { get; set; }

        public static string Settings = "-cilmH";

        protected override void ProcessRecord()
        {
            string opt = "-";

            if (string.IsNullOrEmpty(Options))
            {
                if (All.IsPresent)          opt += "a";
                if (Color.IsPresent)        opt += "c";
                if (Icons.IsPresent)        opt += "i";
                if (List.IsPresent)         opt += "l";
                if (CreationTime.IsPresent) opt += "C";
                if (ModifiedTime.IsPresent) opt += "m";
                if (AccessTime.IsPresent)   opt += "A";
                if (Hour.IsPresent)         opt += "H";
                if (Headers.IsPresent)      opt += "h";
            }
            else opt += Options;

            if (SetDefault.IsPresent) Settings = opt;
            if (NoOutput.IsPresent) return;

            opt = opt == "-" ? Settings : opt;

            string curdir = SessionState.Path.CurrentLocation.Path;
            string response = Helpers.ServerListDir(Path, curdir, opt);
            if (response.Length > 0) WriteObject(response);
        }
    }

    [Cmdlet(VerbsCommon.Get, "ShellServerListDirAll")]
    [Alias("la")]
    [OutputType(typeof(string))]
    public class ListDirAllCmd : PSCmdlet
    {
        [Parameter(Position = 0)]
        [ArgumentCompleter(typeof(DirsCompleter))]
        public string Path { get; set; }

        protected override void ProcessRecord()
        {
            string curdir = SessionState.Path.CurrentLocation.Path;
            string response = Helpers.ServerListDir(Path, curdir, "-acilmCHh");
            if (response.Length > 0) WriteObject(response);
        }
    }

    [Cmdlet(VerbsCommon.Search, "ShellServerHistory")]
    [OutputType(typeof(string))]
    public class HistoryCmd : PSCmdlet
    {
        [Parameter()]
        [Alias("C")]
        public SwitchParameter CaseSensitive {get; set;}

        [Parameter()]
        [Alias("A")]
        public SwitchParameter All {get; set;}

        [Parameter()]
        [Alias("AC", "CA", "B")]
        public SwitchParameter Both {get; set;}

        [Parameter(
                Mandatory = true,
                ValueFromRemainingArguments = true)]
        public string[] Args;

        protected override void ProcessRecord()
        {
            string opt = "";

            if (CaseSensitive.IsPresent) opt += 'c';
            if (All.IsPresent) opt += 'a';
            if (Both.IsPresent) opt = "ac";

            int width = Host.UI.RawUI.BufferSize.Width;
            int height = Host.UI.RawUI.BufferSize.Height;
            string sendArgs = string.Join(';', Args);

            Globals.SendToServer($"7{width};{height};{opt};{sendArgs}");
            string response = Globals.ReceiveFromServer();
            if (response.Length > 0) WriteObject(response);
        }
    }
   
    [Cmdlet(VerbsLifecycle.Invoke, "ShellServerEnterKeyHandler")]
    [OutputType(typeof(void))]
    public class EnterKeyHandlerCmd : PSCmdlet
    {
        static bool isIncomplete;
        static bool prevWasIncomplete;

        protected override void ProcessRecord()
        {
            ReadLine.Invoke(
                    ReadLine.GetBufferState,
                    ref ReadLine.GetBufferStateArgs
            );
            
            var ast = ReadLine.GetBufferStateArgs[0] as Ast;
            var err = ReadLine.GetBufferStateArgs[2] as ParseError[];
            var line = ast.Extent.Text;

            prevWasIncomplete = isIncomplete;
            isIncomplete = false;

            foreach (ParseError e in err)
            {
                if (e.IncompleteInput)
                {
                    isIncomplete = true;
                    break;
                }
            }

            if (!prevWasIncomplete)
            {
                var cursorPosition = Console.GetCursorPosition();

                int width = Host.UI.RawUI.BufferSize.Width;
                int printableFirstLine = width - 2;  // `❯ `
                int prompt_lines = 2;
                int lineLength = line.Length;

                if (lineLength > printableFirstLine)
                {
                    prompt_lines++;
                    lineLength -= printableFirstLine;
                    prompt_lines += lineLength / width;
                }

                int top = Math.Max(0, cursorPosition.Top - prompt_lines);

                Console.SetCursorPosition(0, top);

                // Sending objects through the pipeline won't work.
                // Seems like wrapping this invocation in 
                // `Set-PSReadLineKeyHandler` script block
                // won't let anything out.
                Console.Write($"\x1b[J\x1b[34m❯\x1b[0m {line}");

                // Have to reset to same `Left` position so PSReadLine 
                // (I think) won't put an extra new line between the
                // last command we just rewrote and the output.
                // It happens if the cursor is not in the end of the
                // output when Enter is pressed.
                Console.SetCursorPosition(
                        cursorPosition.Left, top + prompt_lines - 2
                );
            }

            ReadLine.Invoke(
                    ReadLine.ValidateAndAcceptLine,
                    ref ReadLine.ValidateAndAcceptLineArgs
            );
        }
    }

    [Cmdlet(VerbsCommon.Switch, "ShellServerTheme")]
    [OutputType(typeof(void))]
    public class ThemeCmd : PSCmdlet
    {
        [Parameter(ValueFromRemainingArguments = true)]
        [ValidateSet("terminal", "system", "blue", "readline", "prompt")]
        public string[] Args;

        protected override void ProcessRecord()
        {
            foreach (string opt in Args)
            {
                if (opt.ToLower() == "readline")
                {
                    ref var readlineThemeArg = ref Globals.lightColors;
                    if (Globals.isLight)
                    {
                        readlineThemeArg = ref Globals.darkColors;
                    }

                    ReadLine.SetReadLineTheme(ref readlineThemeArg);
                    Globals.isLight = !Globals.isLight;
                    continue;
                }

                Globals.SendToServer($"6{opt}");
            }
        }
    }

    [Cmdlet(VerbsCommon.Switch, "ShellServerTimeout")]
    [OutputType(typeof(void))]
    public class TimeoutCmd : PSCmdlet
    {
        [Parameter(Position = 0, Mandatory = true)]
        public int MilliSeconds {get; set;}
   
        protected override void ProcessRecord()
        {
            Globals.client.Client.ReceiveTimeout = MilliSeconds;
        }
    }
   
    [Cmdlet(VerbsCommon.Switch, "ShellServerOptions")]
    [OutputType(typeof(void))]
    public class OptionsCmd : PSCmdlet
    {
        [Parameter(
                Mandatory = true,
                ValueFromRemainingArguments = true)]
        [ValidateSet(
                "timeit",
                "no-timeit",
                "trackdir",
                "no-trackdir",
                "fallback",
                "no-fallback",
                "watchdog",
                "no-watchdog",
                "disable-git",
                "enable-git",
                "use-gitstatus",
                "use-git",
                "use-pygit2",
                "test-status",
                "no-test-status",
                "linear",
                "no-linear",
                "read-async",
                "no-read-async",
                "let-crash")]
        public string[] Args;
   
        protected override void ProcessRecord()
        {
            foreach (string opt in Args) Globals.SendToServer($"2Set{opt}");
        }
    }
   
    [Cmdlet(VerbsCommon.Get, "ShellServerBuffer")]
    [OutputType(typeof(string))]
    public class BufferCmd : PSCmdlet
    {
        [Parameter()]
        [Alias("k")]
        public SwitchParameter Keep {get; set;}
   
        protected override void ProcessRecord()
        {
            string opt = "";
            if (Keep.IsPresent) opt += 'k';
   
            Globals.SendToServer($"8{opt}");
            string response = Globals.ReceiveFromServer();
            if (response.Length > 0) WriteObject(response);
        }
    }

    [Cmdlet(VerbsCommon.Get, "ShellServerConfig")]
    public class ConfigCmd : PSCmdlet
    {
        protected override void ProcessRecord()
        {
            string[] configs;

            Globals.SendToServer("2Conf");
            configs = Globals.ReceiveFromServer().TrimEnd('\n').Split("\n");

            foreach (string config in configs)
            {
                string[] splitted = config.Split(';');

                WriteObject(new ConfigResult{
                    Config = splitted[0],
                    Value = splitted[1]
                });
            }
        }
    }

    public class ConfigResult
    {
        public string Config { get; set; }
        public string Value  { get; set; }
    }
}
