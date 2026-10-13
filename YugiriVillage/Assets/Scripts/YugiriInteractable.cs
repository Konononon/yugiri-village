using UnityEngine;

namespace Yugiri.Gameplay
{
    public class YugiriInteractable : MonoBehaviour
    {
        public string titleJp = "夕霧村 停留所";
        public string promptText = "[E] 조사하기";
        [TextArea(2, 5)]
        public string inspectDialogue = "오래된 시간표가 녹슨 철판에 붙어 있다.";
        public AudioClip interactSfx;
        public AudioClip horrorStingerSfx;
        public bool triggersShrineEvent = false;
    }
}
