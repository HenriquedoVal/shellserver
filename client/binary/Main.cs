using System;
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
        public static readonly string admin =
            IsUserAnAdmin() ? "(Admin) " : "";

        public static readonly string HOME =
            Environment.GetEnvironmentVariable("USERPROFILE");

        const short port = 5432;

        public static UdpClient client = new UdpClient();
        public static IPEndPoint endpoint = new IPEndPoint(
                IPAddress.Loopback, port
        );
        public static UTF8Encoding encoder = new UTF8Encoding();

        public static bool isLight = false;
        public static bool firstPrompt = true;

        public static string[] pathCmdCompletions;

        public static Hashtable lightColors;
        public static Hashtable darkColors;

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

        public void OnRemove(PSModuleInfo modInfo)
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

            colors["Command"]                = "DarkYellow"  ;
            colors["Comment"]                = "\x1b[90m"    ;
            colors["ContinuationPrompt"]     = "DarkGray"    ;
            colors["DefaultToken"]           = "DarkGray"    ;
            colors["Emphasis"]               = "DarkBlue"    ;
            colors["InlinePrediction"]       = "DarkGray"    ;
            colors["Keyword"]                = "Green"       ;
            colors["ListPrediction"]         = "DarkYellow"  ;
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

        public static void ExitHandler(object sender, EventArgs e)
        {
            SendToServer("2Exit");
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

        [DllImport("shell32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsUserAnAdmin();
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
            var arg = new object[0];
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
            
            ShellServerFuzzyPredictor.container = new List<ValueTuple<int, Tuple<string, string>>>();

            string response = Globals.ReceiveFromServer();
            string[] paths = response.Split('\n');

            foreach (string fullPath in paths)
            {
                string lastPath = fullPath.Substring(
                        fullPath.LastIndexOf('\\') + 1
                );
            
                if (lastPath.Length == 0) lastPath = fullPath;
            
                ShellServerFuzzyPredictor.container.Add((20, Tuple.Create(lastPath, fullPath)));
            }

        }
        public static string ServerListDir(
                string path, string curdir, string opt
        )
        {
            string target;

            if (path is null) target = curdir;
            else target = System.IO.Path.Combine(curdir, path);
            
            string msg = $"5{opt};{target}";

            Globals.SendToServer(msg);
            return Globals.ReceiveFromServer();
        }

        public static void ToggleReadLineTheme()
        {
            if (Globals.isLight)
            {
                ReadLine.SetReadLineTheme(ref Globals.darkColors);
                Globals.isLight = false;
                return;
            }

            ReadLine.SetReadLineTheme(ref Globals.lightColors);
            Globals.isLight = true;
        }

        public static int GetDamerauLevenshteinDistance(string s, string t)
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
    }

    class PathCmdCompleter: IArgumentCompleter
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
                yield return new CompletionResult(
                        comp, comp,
                        CompletionResultType.ParameterValue,
                        comp
                );
            }

            var fallBack = CompletionCompleters.CompleteFilename(wordToComplete);
            foreach (var res in fallBack)
            {
                string fullPath = res.ToolTip;
                var attr = System.IO.File.GetAttributes(fullPath);
                bool isDir = (attr & System.IO.FileAttributes.Directory) > 0;
                
                if (isDir) yield return res;
            }
        }
    }

    public class ShellServerFuzzyPredictor : ICommandPredictor
    {
        // List<(distance, (lastPath, fullPath))>
        public static List<ValueTuple<int, Tuple<string, string>>> container;
        readonly List<string> cmds = new List<string> {"pz", "set-shellserverpathfuzzy"};

        private object _optionsInst;
        private object _userStyle;
        private PropertyInfo _predictionSourceProperty;

        private readonly Guid _guid;

        internal ShellServerFuzzyPredictor(string guid)
        {
            _guid = new Guid(guid);

            var arg = new object[0];
            _optionsInst = ReadLine.Invoke(
                    ReadLine.GetOptions,
                    ref arg
            ) ;
            _predictionSourceProperty = _optionsInst.GetType().GetProperty("PredictionSource");

            _userStyle = _predictionSourceProperty.GetValue(
                    _optionsInst
            );
        }

        public static void SortContainer(string args)
        {
            for (int i = 0; i < container.Count; i++)
            {
                int dld = Helpers.GetDamerauLevenshteinDistance(
                        args, container[i].Item2.Item1
                );
                container[i] = (dld, container[i].Item2);
            }

            container.Sort();
        }

        public Guid Id => _guid;

        public string Name => "ShellServer";

        public string Description => "Provides prediction for the `Set-ShellServerPathFuzzy` Cmdlet.";

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

            PathFuzzyCmd.chosenPath = container[0].Item2.Item2;
            int min = container[0].Item1;

            var res = new List<PredictiveSuggestion>();

            for (int i = 0; i < container.Count; i++)
            {
                var target = container[i];
                if (target.Item1 == min)
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
    public class PromptCmd : PSCmdlet
    {
        
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

            width -= Globals.admin.Length;

            Globals.SendToServer($"1{question}{path};{width};{duration}");

            string prompt;

            try
            {
                prompt = Globals.ReceiveFromServer();
            }
            catch (SocketException e)
            {
                Console.WriteLine(
                    "Server didn't respond in time. Press Enter to return to previous prompt."
                );
               
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

            if (Globals.firstPrompt)
            {
                new Thread(new ThreadStart(Globals.ThreadInit)).Start();
                Globals.firstPrompt = false;
            }

            char changed = prompt[0];
            prompt = prompt.Substring(1);

            if (changed == '1')
            {
                new Thread(new ThreadStart(Helpers.UpdateCompletions)).Start();
            }

            WriteObject($"\n\x1b[31m{Globals.admin}\x1b[32m{venv}{prompt}");
        }
    }
    
    [Cmdlet(VerbsCommon.Set, "ShellServerPath")]
    [Alias("p")]
    public class PathCmd : PSCmdlet
    {
        [Parameter()]
        [Alias("A")]
        public SwitchParameter Add {get; set;}

        [Parameter()]
        [Alias("O")]
        public SwitchParameter Output {get; set;}

        [Parameter()]
        [Alias("J")]
        public SwitchParameter Junction {get; set;}

        [Parameter(ValueFromRemainingArguments = true)]
        [ArgumentCompleter(typeof(PathCmdCompleter))]
        public string[] Path;

        void HandleAdd(string joinedPath, string curdir)
        {
            if (Output.IsPresent)
            {
                WriteWarning("The `Output` option was ignored.");
            }

            if (Junction.IsPresent)
            {
                WriteWarning("The `Junction` option was ignored.");
            }

            string target;

            if (joinedPath is null)
            {
                target = curdir;
            }
            else
            {
                target = System.IO.Path.Combine(curdir, joinedPath);
            }

            if (System.IO.Path.Exists(target))
            {
                Globals.SendToServer($"9{target}");
                return;
            }

            WriteError(
                new ErrorRecord(
                    new ArgumentException("No match found."),
                    "No existing relative or full paths matches arg.",
                    ErrorCategory.ObjectNotFound,
                    null
                )
            );
        }

        void HandleJunction(string joinedPath, string curdir)
        {
            if (Output.IsPresent)
            {
                WriteWarning("The `Output` option was ignored.");
            }

            string target;

            if (string.IsNullOrEmpty(joinedPath))
            {
                target = curdir;
            }
            else
            {
                target = System.IO.Path.Combine(
                    curdir, joinedPath);
            }

            if (!System.IO.Path.Exists(target))
            {
                WriteError(
                    new ErrorRecord(
                        new ArgumentException($"{target} not found."),
                        "Given path doesn't exists.",
                        ErrorCategory.ObjectNotFound,
                        null
                    )
                );
                return;
            }

            var attr = System.IO.File.GetAttributes(target);

            bool isJunction = (attr & System.IO.FileAttributes.ReparsePoint) > 0;
            bool isDir = (attr & System.IO.FileAttributes.Directory) > 0;

            if (isDir && isJunction)
            {
                SessionState.Path.SetLocation(
                    System.IO.Directory.ResolveLinkTarget(target, false).FullName
                );
                return;
            }

            WriteObject("No Junction found.");
        }

        protected override void ProcessRecord()
        {
            if (Path is null) Path = new string[0];

            string joinedPath = string.Join(' ', Path);
            string curdir = SessionState.Path.CurrentLocation.Path;
            string target;

            if (joinedPath.StartsWith(".\\"))
            {
                joinedPath = joinedPath.TrimStart('.').TrimStart('\\');
            }
            joinedPath = joinedPath.TrimEnd('\\');

            if (Add.IsPresent)
            {
                HandleAdd(joinedPath, curdir);
                return;
            }

            if (Junction.IsPresent)
            {
                HandleJunction(joinedPath, curdir);
                return;
            }

            if (string.IsNullOrEmpty(joinedPath))
            {
                SessionState.Path.SetLocation(Globals.HOME);
                return;
            }

            target = $"3{joinedPath}";

            Globals.SendToServer(target);
            string response = Globals.ReceiveFromServer();

            if (Output.IsPresent)
            {
                if (!string.IsNullOrEmpty(response))
                {
                    WriteObject(response);
                }
                else
                {
                    WriteError(
                        new ErrorRecord(
                            new ArgumentException("No match found."),
                            "Argument not found in server's list of paths.",
                            ErrorCategory.ObjectNotFound,
                            null
                        )
                    );
                }
                return;
            }

            if (!string.IsNullOrEmpty(response))
            {
                SessionState.Path.SetLocation(response);
                return;
            }

            if (
                    System.IO.Path.Exists(
                        System.IO.Path.Combine(
                            SessionState.Path.CurrentLocation.Path,
                            joinedPath))
            )
            {
                SessionState.Path.SetLocation(joinedPath);
                return;
            }

            WriteError(
                new ErrorRecord(
                    new ArgumentException("No match found."),
    "Argument not found in server's list of paths nor corresponds to existing relative or full path.",
                    ErrorCategory.ObjectNotFound,
                    null
                )
            );
        }
    }

    [Cmdlet(VerbsCommon.Set, "ShellServerPathFuzzy")]
    [Alias("pz")]
    public class PathFuzzyCmd : PSCmdlet
    {
        [Parameter(ValueFromRemainingArguments = true, Mandatory = true)]
        [ArgumentCompleter(typeof(PathCmdCompleter))]
        public string[] Query;

        public static string chosenPath;

        protected override void ProcessRecord()
        {
            string lastArg = Query[Query.Length - 1];

            // If the predictor wasn't used, if it was invoked from history.
            if (chosenPath is null)
            {
                if (System.IO.Path.IsPathFullyQualified(lastArg))
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
        [Parameter(Position = 0)]
        public string Path { get; set; }

        protected override void ProcessRecord()
        {
            string curdir = SessionState.Path.CurrentLocation.Path;
            string response = Helpers.ServerListDir(Path, curdir, "-cil");
            if (response.Length > 0) WriteObject(response);
        }
    }

    [Cmdlet(VerbsCommon.Get, "ShellServerListDirAll")]
    [Alias("la")]
    [OutputType(typeof(string))]
    public class ListDirAllCmd : PSCmdlet
    {
        [Parameter(Position = 0)]
        public string Path { get; set; }

        protected override void ProcessRecord()
        {
            string curdir = SessionState.Path.CurrentLocation.Path;
            string response = Helpers.ServerListDir(Path, curdir, "-acil");
            if (response.Length > 0) WriteObject(response);
        }
    }

    [Cmdlet(VerbsCommon.Search, "ShellServerHistory")]
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
    public class EnterKeyHandlerCmd : PSCmdlet
    {
        static bool wasIncomplete = false;
        static bool prevWasIncomplete = false;

        protected override void ProcessRecord()
        {
            ReadLine.Invoke(
                    ReadLine.GetBufferState,
                    ref ReadLine.GetBufferStateArgs
            );
            
            var ast = (Ast)ReadLine.GetBufferStateArgs[0];

            var line = ast.Extent.Text;
            var err = (ParseError[])ReadLine.GetBufferStateArgs[2];
            var cursor = (int)ReadLine.GetBufferStateArgs[3];

            prevWasIncomplete = wasIncomplete;
            wasIncomplete = false;

            foreach (ParseError e in err)
            {
                if (e.IncompleteInput)
                {
                    wasIncomplete = true;
                    break;
                }
            }

            if (!prevWasIncomplete)
            {
                Console.SetCursorPosition(
                        0, Console.GetCursorPosition().Top - 2);

                // Sending objects through the pipeline won't work.
                // Seems like wrapping this invocation in 
                // `Set-PSReadLineKeyHandler` script block
                // won't let anything out.
                Console.Write($"\x1b[J\x1b[34m❯\x1b[0m {line}");
            }

            ReadLine.Invoke(
                    ReadLine.ValidateAndAcceptLine,
                    ref ReadLine.ValidateAndAcceptLineArgs
            );
        }
    }

    [Cmdlet(VerbsCommon.Switch, "ShellServerTheme")]
    public class ThemeCmd : PSCmdlet
    {
        [Parameter(ValueFromRemainingArguments = true)]
        [ValidateSet("terminal", "system", "blue", "readline")]
        public string[] Args;

        protected override void ProcessRecord()
        {
            foreach (string opt in Args)
            {
                if (opt.ToLower() == "readline")
                {
                    Helpers.ToggleReadLineTheme();
                    continue;
                }

                Globals.SendToServer($"6{opt}");
            }
        }
    }

    [Cmdlet(VerbsCommon.Switch, "ShellServerTimeout")]
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
#if DEBUG
    [Cmdlet(VerbsDiagnostic.Test, "test")]
    public class Test : PSCmdlet
    {
        protected override void ProcessRecord()
        {
            var fallBack = CompletionCompleters.CompleteFilename("some");
            foreach (var any in fallBack)
            {
                WriteObject(any.ResultType);
                WriteObject(any.ListItemText);
                WriteObject(any.CompletionText);
                WriteObject(any.ToolTip);
                WriteObject(any.GetType().ToString());
            }

        }
    }
#endif
}
