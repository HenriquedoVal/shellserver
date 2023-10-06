using System;
using System.IO;
using System.Threading;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;

using System.Management.Automation;
using System.Management.Automation.Language;
using System.Management.Automation.Runspaces;
using System.Management.Automation.Subsystem;

using Microsoft.Win32;
using Microsoft.PowerShell.Commands;


namespace ShellServer
{
    public class Globals : IModuleAssemblyInitializer, IModuleAssemblyCleanup
    {
        const short port = 5432;

        public static UdpClient client;
        public static string[,] lightColors;
        public static string[,] darkColors;
        public static string[] pathCmdCompletions;
        public static bool isLight;

        static IPEndPoint endpoint = new IPEndPoint(
                IPAddress.Loopback, port
        );
        static UTF8Encoding encoder = new UTF8Encoding();

        private const string predictorIdentifier = "ce865750-f55b-4bf6-a302-fcba803b1442";

        public void OnImport()
        {
            client = new UdpClient();
            client.Connect(IPAddress.Loopback, port);
            SendToServer("2InitpwshBin");

            Runspace.DefaultRunspace.Events.SubscribeEvent(
                 null, null, PSEngineEvent.Exiting, null,
                 new PSEventReceivedEventHandler(ExitHandler),
                 false, false
            );
        // }
        //
        // public static void ThreadInit()
        // {
        
            try {
                Helpers.UpdateCompletions();
            } catch (SocketException) {
                Remove();
                throw;
            }

            ReadLine.SetUp();

            lightColors = new string[,] {
                { "Command"               , "\x1b[93m"    },
                { "Comment"               , "\x1b[92m"    },
                { "ContinuationPrompt"    , "\x1b[94m"    },
                { "DefaultToken"          , "\x1b[97m"    },
                { "Emphasis"              , "\x1b[96m"    },
                { "InlinePrediction"      , "\x1b[90m"    },
                { "Keyword"               , "\x1b[92m"    },
                { "ListPrediction"        , "\x1b[33m"    },
                { "ListPredictionSelected", "\x1b[34;238m"},
                { "Member"                , "\x1b[34m"    },
                { "Number"                , "\x1b[34m"    },
                { "Operator"              , "DarkGray"    },
                { "Parameter"             , "DarkGray"    },
                { "Selection"             , "\x1b[34;238m"},
                { "String"                , "DarkCyan"    },
                { "Type"                  , "\x1b[32m"    },
                { "Variable"              , "Green"       },
            };

            darkColors = new string[,] {
                { "Command"               , "\x1b[93m"      },
                { "Comment"               , "\x1b[32m"      },
                { "ContinuationPrompt"    , "\x1b[34m"      },
                { "DefaultToken"          , "\x1b[37m"      },
                { "Emphasis"              , "\x1b[96m"      },
                { "InlinePrediction"      , "\x1b[38;5;238m"},
                { "Keyword"               , "\x1b[92m"      },
                { "ListPrediction"        , "\x1b[33m"      },
                { "ListPredictionSelected", "\x1b[48;5;238m"},
                { "Member"                , "\x1b[97m"      },
                { "Number"                , "\x1b[97m"      },
                { "Operator"              , "\x1b[90m"      },
                { "Parameter"             , "\x1b[90m"      },
                { "Selection"             , "\x1b[30;47m"   },
                { "String"                , "\x1b[36m"      },
                { "Type"                  , "\x1b[34m"      },
                { "Variable"              , "\x1b[92m"      },
            };

            const string subKey = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize";

            using (var key = Registry.CurrentUser.OpenSubKey(subKey, false))
            {
                var value = key?.GetValue("SystemUsesLightTheme");
                if ((int)value == 1) isLight = true;
            }

            if (isLight)
            {
                ReadLine.SetReadLineTheme(lightColors);
            }
            
            ReadLine.StackOption("PromptText", new string[] {"❯ "});
            ReadLine.SetOptions();

            ReadLine.SetKeyHandler(
                    Key: "Enter",
                    scriptBlock: "Invoke-ShellServerEnterKeyHandler",
                    Description: "ShellServer Module Enter key handler"
            );

            client.Client.ReceiveTimeout = 3000;

            var predictor = new ShellServerFuzzyPredictor(predictorIdentifier);
            SubsystemManager.RegisterSubsystem(SubsystemKind.CommandPredictor, predictor);
        }

        public void OnRemove(PSModuleInfo psModuleInfo) => Remove();

        static void ExitHandler(object sender, EventArgs e) => Remove();

        public static void Remove()
        {
            try {
                SendToServer("2Exit");
                client.Dispose();
            } catch (Exception) {}

            try {
                SubsystemManager.UnregisterSubsystem(
                        SubsystemKind.CommandPredictor, new Guid(predictorIdentifier)
                );
            } catch (Exception) {}

            try {
                ScriptBlock.Create(
                    "Set-PSReadLineKeyHandler -Key Enter -Function AcceptLine"
                ).Invoke();

                ScriptBlock.Create(
                    "Remove-Alias -Name prompt"
                ).Invoke();
            } catch (Exception) {}
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


    [Cmdlet(VerbsLifecycle.Invoke, "ShellServerPrompt")]
    [Alias("prompt")]
    [OutputType(typeof(void))]
    public class PromptCmd : PSCmdlet
    {
        static readonly string admin =
            IsUserAnAdmin() ? "(Admin) " : "";
        
        // static bool firstPrompt = true;

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
                string msg = "Server didn't respond in time. "
                    + "Press Enter to return to previous prompt.";

                Console.WriteLine(msg);
               
                WriteError(
                    new ErrorRecord(
                        e,
                        "Server didn't respond in time.",
                        ErrorCategory.OperationTimeout,
                        null
                    )
                );

                Globals.Remove();
                return;
            }

            // if (firstPrompt)
            // {
            //     new Thread(new ThreadStart(Globals.ThreadInit)).Start();
            //     firstPrompt = false;
            // }

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
        static bool isValid;
        static bool prevWasValid;
        static Ast  prevAst;

        protected override void ProcessRecord()
        {
            prevAst = ReadLine.BufferState[0] as Ast;
            prevWasIncomplete = isIncomplete;
            isIncomplete = false;

            ReadLine.GetBufferState();

            var err = ReadLine.BufferState[2] as ParseError[];
            foreach (ParseError e in err)
            {
                if (e.IncompleteInput)
                {
                    isIncomplete = true;
                    break;
                }
            }

            if (prevWasIncomplete)
            {
                ReadLine.ValidateAndAcceptLine();
                return;
            }

            prevWasValid = isValid;
            isValid = ReadLine.Validate() == null;

            var ast = ReadLine.BufferState[0] as Ast;
            var line = ast.Extent.Text;

            bool sameAst = prevAst?.Extent.Text == line;
            bool valid = isValid || (!isValid && !prevWasValid && sameAst);

            if (!valid && !isIncomplete)
            {
                ReadLine.ValidateAndAcceptLine();
                return;
            }

            var cursorPosition = Console.GetCursorPosition();

            int width = Host.UI.RawUI.BufferSize.Width;
            int printableFirstLine = width - 2;  // `❯ `
            int promptLines = 2;
            int lineLength = line.Length;

            if (lineLength > printableFirstLine)
            {
                promptLines++;
                lineLength -= printableFirstLine;
                promptLines += lineLength / width;
            }

            int top = Math.Max(0, cursorPosition.Top - promptLines);

            Console.SetCursorPosition(0, top);

            // Sending objects through the pipeline won't work.
            // Seems like wrapping this invocation in 
            // `Set-PSReadLineKeyHandler` script block
            // won't let anything out.
            Console.Write($"\x1b[J");
            if (!string.IsNullOrEmpty(line))
            {
                Console.Write($"\x1b[34m❯\x1b[0m {line}");
            }

            // Have to reset to same `Left` position so PSReadLine 
            // (I think) won't put an extra new line between the
            // last command we just rewrote and the output.
            // It happens if the cursor is not in the end of the
            // output when Enter is pressed.
            Console.SetCursorPosition(
                    cursorPosition.Left, top + promptLines - 2
            );

            ReadLine.ValidateAndAcceptLine();
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
                    var readlineThemeArg = Globals.lightColors;
                    if (Globals.isLight)
                    {
                        readlineThemeArg = Globals.darkColors;
                    }

                    ReadLine.SetReadLineTheme(readlineThemeArg);

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
                string[] split = config.Split(';');

                WriteObject(new ConfigResult{
                    Config = split[0],
                    Value = split[1]
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
