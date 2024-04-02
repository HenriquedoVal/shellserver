using System;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Collections.Generic;

using System.Management.Automation;
using System.Management.Automation.Language;
using System.Management.Automation.Subsystem.Prediction;


namespace ShellServer
{
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

			_optionsInst = ReadLine.GetOptions();
            _predictionSourceProperty = _optionsInst.GetType().GetProperty("PredictionSource");

            _userStyle = _predictionSourceProperty.GetValue(_optionsInst);
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
}
