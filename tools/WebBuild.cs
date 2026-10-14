using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Yugiri.WebExport
{
    // Copied into an isolated build project by build-web.ps1.
    public static class WebBuild
    {
        public static void Build()
        {
            var output = Environment.GetEnvironmentVariable("YUGIRI_WEB_OUTPUT");
            if (string.IsNullOrEmpty(output)) throw new Exception("YUGIRI_WEB_OUTPUT is required.");
            if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.WebGL, BuildTarget.WebGL))
                throw new Exception("WebGL Build Support is not installed.");

            PlayerSettings.SetScriptingBackend(NamedBuildTarget.WebGL, ScriptingImplementation.IL2CPP);
            PlayerSettings.SetIl2CppCodeGeneration(NamedBuildTarget.WebGL, Il2CppCodeGeneration.OptimizeSize);
            PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.Low);
            PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Gzip;
            PlayerSettings.WebGL.decompressionFallback = false;
            PlayerSettings.WebGL.nameFilesAsHashes = true;
            PlayerSettings.WebGL.dataCaching = true;
            PlayerSettings.WebGL.threadsSupport = false;
            PlayerSettings.WebGL.initialMemorySize = 256;
            PlayerSettings.WebGL.maximumMemorySize = 2048;
            PlayerSettings.WebGL.webAssemblyBigInt = true;
            PlayerSettings.WebGL.webAssemblyTable = true;
            EditorUserBuildSettings.development = false;

            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            if (scenes.Length == 0) throw new Exception("No enabled build scenes.");
            Directory.CreateDirectory(output);
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = scenes,
                locationPathName = output,
                target = BuildTarget.WebGL,
                options = BuildOptions.None
            });
            var summary = report.summary;
            Debug.Log($"YUGIRI_WEB_BUILD: {summary.result}, {summary.totalSize} bytes, {summary.totalTime}");
            if (summary.result != BuildResult.Succeeded)
                throw new Exception($"Web build failed: {summary.totalErrors} errors.");
        }
    }
}
