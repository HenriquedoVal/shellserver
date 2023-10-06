using System;
using System.Reflection;
using System.Management.Automation;
using System.Management.Automation.Language;


namespace ShellServer
{
    class ReadLine
    {
        static Type PSConsoleReadLine;
        static Type SetPSReadLineOption;

		static object singleton;

		static MethodInfo _ValidateAndAcceptLine;
		static MethodInfo _SetOptions;
		static MethodInfo _Validate;
		
		static object[] _AcceptLineDefaultArg = {null, null};
		static object[] _GetOptDefaultArg = Array.Empty<object>();
		static object _optionsInstance;

        public static object[] BufferState = new object[4];

		public static void SetUp()
		{
			var Asm = AppDomain.CurrentDomain.Load(
				"Microsoft.PowerShell.PSReadLine2"
			);

            PSConsoleReadLine = Asm.GetType("Microsoft.PowerShell.PSConsoleReadLine");
            SetPSReadLineOption = Asm.GetType("Microsoft.PowerShell.SetPSReadLineOption");

			if (
					PSConsoleReadLine is null
					|| SetPSReadLineOption is null
			)
				throw new Exception("Types not found");

			singleton = PSConsoleReadLine.GetField(
					"_singleton",
					BindingFlags.Static | BindingFlags.NonPublic
			).GetValue(null);

			_ValidateAndAcceptLine = PSConsoleReadLine.GetMethod("ValidateAndAcceptLine");
			_SetOptions = PSConsoleReadLine.GetMethod("SetOptions");

			_Validate   = PSConsoleReadLine.GetMethod(
				"Validate", BindingFlags.NonPublic | BindingFlags.Instance
			);
		}

        static object? _Invoke(string methodName, object[] args)
        {
            return PSConsoleReadLine.InvokeMember(
                    methodName,
                    BindingFlags.InvokeMethod,
                    Type.DefaultBinder,
                    null,
                    args
            );
        }

        public static void SetReadLineTheme(string[,] colors)
        {
            var arg = Array.Empty<object>();
            var inst = GetOptions();

			for (int i = 0; i < colors.Length / 2; i++)
			{
				inst.GetType().InvokeMember(
					colors[i, 0] + "Color",
                    BindingFlags.Public | BindingFlags.SetProperty | BindingFlags.Instance,
                    Type.DefaultBinder,
                    inst,
                    new object[] {colors[i, 1]}
				);
			}
        }

		public static void StackOption(string Property, object Value)
		{
			if (_optionsInstance is null)
				_optionsInstance = Activator.CreateInstance(SetPSReadLineOption);
			var prop = SetPSReadLineOption.GetProperty(Property);
			if (prop is null) throw new Exception($"Property {Property} is null.");
			prop.SetValue(_optionsInstance, Value);
		}

		public static void SetOptions()
		{
			_SetOptions.Invoke(null, new object[] {_optionsInstance});
			_optionsInstance = null;
		}
		
		public static void ValidateAndAcceptLine() =>
			_ValidateAndAcceptLine.Invoke(null, _AcceptLineDefaultArg); 

		public static void SetKeyHandler(string Key, string scriptBlock, string Description)
		{
            var handler = new object[4];
			handler[0] = new string[] {Key};
            handler[1] = ScriptBlock.Create(scriptBlock);
            handler[2] = Description;
            handler[3] = "";

			_Invoke("SetKeyHandler", handler);
		}

		public static void GetBufferState() =>
			_Invoke("GetBufferState", BufferState);

		public static object GetOptions()
		{
			return _Invoke("GetOptions", _GetOptDefaultArg);
		}
		
		public static string Validate()
		{
			return _Validate.Invoke(
					singleton, new object[] {BufferState[0] as Ast}
			) as string;
		}
    }
}
