using UnityEngine;

namespace Yugiri.Gameplay
{
    public class YugiriLightFlicker : MonoBehaviour
    {
        public enum FlickerStyle
        {
            CandleFlame,
            FluorescentHum,
            DamagedStreetlamp
        }

        public FlickerStyle style = FlickerStyle.CandleFlame;
        public float baseIntensity = 1.8f;
        public float amplitude = 0.25f;
        public float speed = 4.5f;
        public float seedOffset = 0f;

        private Light _light;
        private Vector3 _baseLocalPos;

        private void Awake()
        {
            _light = GetComponent<Light>();
            _baseLocalPos = transform.localPosition;
            if (seedOffset == 0f)
            {
                seedOffset = Random.Range(0f, 100f);
            }
        }

        private void Update()
        {
            if (_light == null) return;
            float t = Time.time * speed + seedOffset;

            if (style == FlickerStyle.CandleFlame)
            {
                float n = Mathf.PerlinNoise(t, seedOffset) * 2f - 1f;
                _light.intensity = Mathf.Max(0.1f, baseIntensity + n * amplitude);
                transform.localPosition = _baseLocalPos + new Vector3(
                    (Mathf.PerlinNoise(t * 1.3f, 1f) - 0.5f) * 0.02f,
                    (Mathf.PerlinNoise(1f, t * 1.7f) - 0.5f) * 0.02f,
                    0f
                );
            }
            else if (style == FlickerStyle.FluorescentHum)
            {
                float buzz = Mathf.Sin(Time.time * 60f) * 0.03f;
                float dip = Mathf.PerlinNoise(t * 2.2f, seedOffset) < 0.12f ? -amplitude : 0f;
                _light.intensity = Mathf.Max(0.15f, baseIntensity + buzz + dip);
            }
            else
            {
                float p = Mathf.PerlinNoise(t * 1.8f, seedOffset);
                float dropout = (p > 0.78f && Mathf.Sin(Time.time * 38f) > 0f) ? -baseIntensity * 0.72f : 0f;
                _light.intensity = Mathf.Max(0.08f, baseIntensity + (p - 0.5f) * amplitude + dropout);
            }
        }
    }
}
