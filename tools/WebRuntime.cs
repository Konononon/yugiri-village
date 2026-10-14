#if UNITY_WEBGL && !UNITY_EDITOR
using UnityEngine;

namespace Yugiri.WebExport
{
    public static class WebRuntime
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Configure()
        {
            Application.runInBackground = true;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 45;
            QualitySettings.pixelLightCount = 12;
            QualitySettings.anisotropicFiltering = AnisotropicFiltering.ForceEnable;
            QualitySettings.shadows = ShadowQuality.All;
            QualitySettings.shadowResolution = ShadowResolution.High;
            QualitySettings.shadowDistance = 38f;
        }
    }
}
#endif
