import React from 'react';

interface AvatarProps {
  emotion: string;
  isSpeaking: boolean;
}

const EMOTION_LABELS: Record<string, string> = {
  neutral: 'Online',
  happy: 'Happy',
  thinking: 'Thinking...',
  sad: 'Pensive',
  surprised: 'Surprised',
  concerned: 'Concerned',
  sleepy: 'Idle',
};

/**
 * Facial expression per emotion. Each entry supplies the eye path (closed lid
 * when `closed` is set), brow transforms, and mouth shape. Values are designed
 * to read clearly at 160x220.
 */
const EMOTION_FACES: Record<
  string,
  {
    eyes: 'open' | 'closed' | 'half';
    browOffset: number;
    browRotate: number;
    mouth: 'smile' | 'flat' | 'open' | 'frown' | 'o' | 'small';
  }
> = {
  neutral: { eyes: 'open', browOffset: 0, browRotate: 0, mouth: 'flat' },
  happy: { eyes: 'open', browOffset: -2, browRotate: -6, mouth: 'smile' },
  thinking: { eyes: 'half', browOffset: -4, browRotate: 8, mouth: 'small' },
  sad: { eyes: 'half', browOffset: 4, browRotate: 10, mouth: 'frown' },
  surprised: { eyes: 'open', browOffset: -8, browRotate: 0, mouth: 'o' },
  concerned: { eyes: 'open', browOffset: -6, browRotate: 6, mouth: 'small' },
  sleepy: { eyes: 'closed', browOffset: 2, browRotate: 0, mouth: 'small' },
};

/* Eye shapes (drawn as paths, centered around x=0 / y=0). */
const EYE_OPEN = 'M -9 0 Q 0 -12 9 0 Q 0 6 -9 0 Z';
const EYE_CLOSED = 'M -9 4 Q 0 -2 9 4';
const EYE_HALF = 'M -9 0 Q 0 -9 9 0 Q 0 4 -9 0 Z';

/* Mouth shapes (paths translated to the mouth center). */
const MOUTH_SMILE = 'M -14 0 Q 0 16 14 0';
const MOUTH_FLAT = 'M -12 0 Q 0 4 12 0';
const MOUTH_OPEN = 'M -10 0 Q 0 14 10 0 Q 0 -6 -10 0 Z';
const MOUTH_FROWN = 'M -14 0 Q 0 -14 14 0';
const MOUTH_O = 'M -6 0 Q 0 10 6 0 Q 0 -10 -6 0 Z';
const MOUTH_SMALL = 'M -7 0 Q 0 5 7 0';

const SPIKE_MS = 90; // speaking mouth animation interval

/** A single loop of the "talking" mouth cycle (open widths). */
const TALK_FRAMES = [0.35, 1.0, 0.55, 0.85, 0.4, 0.7];

export const Avatar: React.FC<AvatarProps> = ({ emotion, isSpeaking }) => {
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    if (!isSpeaking) {
      setFrame(0);
      return;
    }
    const id = setInterval(() => setFrame((f) => (f + 1) % TALK_FRAMES.length), SPIKE_MS);
    return () => clearInterval(id);
  }, [isSpeaking]);

  const face = EMOTION_FACES[emotion] ?? EMOTION_FACES.neutral;
  const eyePath =
    face.eyes === 'closed' ? EYE_CLOSED : face.eyes === 'half' ? EYE_HALF : EYE_OPEN;
  const eyeFill = face.eyes === 'open' ? '#2b2150' : 'none';
  const eyeStroke = face.eyes === 'open' ? 'none' : '#2b2150';

  // While speaking the mouth animates regardless of the base expression.
  const mouthScale = isSpeaking ? TALK_FRAMES[frame] : 1;
  const mouthName = isSpeaking
    ? 'open'
    : (EMOTION_FACES[emotion] ?? EMOTION_FACES.neutral).mouth;

  const mouthShape =
    mouthName === 'smile'
      ? MOUTH_SMILE
      : mouthName === 'open'
        ? MOUTH_OPEN
        : mouthName === 'frown'
          ? MOUTH_FROWN
          : mouthName === 'o'
            ? MOUTH_O
            : mouthName === 'small'
              ? MOUTH_SMALL
              : MOUTH_FLAT;

  const mouthFilled = mouthName === 'open' || mouthName === 'o';

  return (
    <div className="avatar-area">
      <div className="avatar-container">
        <svg
          className="avatar-sprite"
          viewBox="-60 -60 120 120"
          role="img"
          aria-label={`Salieri, ${EMOTION_LABELS[emotion] || emotion}`}
        >
          <defs>
            <linearGradient id="av-body" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#8b7bff" />
              <stop offset="1" stopColor="#4a3cfc" />
            </linearGradient>
            <linearGradient id="av-glow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#c9b8ff" stopOpacity="0.9" />
              <stop offset="1" stopColor="#8b7bff" stopOpacity="0.15" />
            </linearGradient>
          </defs>

          {/* ambient glow behind the head (pulses while talking) */}
          <circle
            r="46"
            fill="url(#av-glow)"
            className={isSpeaking ? 'avatar-glow-talking' : 'avatar-glow-idle'}
          />

          {/* head */}
          <circle cx="0" cy="-14" r="30" fill="url(#av-body)" />

          {/* hair / composer curls */}
          <g fill="#2b2150" stroke="#2b2150" strokeWidth="1.5">
            <path d="M -30 -22 Q -34 -44 -14 -46 Q -4 -48 2 -46" fill="none" />
            <path d="M -22 -40 Q -18 -52 -4 -50 Q 8 -48 14 -42" fill="none" />
            <circle cx="-30" cy="-30" r="5" />
            <circle cx="-12" cy="-42" r="4" />
            <circle cx="6" cy="-44" r="4" />
          </g>

          {/* body / cloak */}
          <path
            d="M -34 16 Q -36 34 -26 40 Q -10 48 0 48 Q 10 48 26 40 Q 36 34 34 16 Z"
            fill="#2b2150"
          />
          <path
            d="M -22 18 Q -24 32 -14 38 Q 0 44 14 38 Q 24 32 22 18 Z"
            fill="url(#av-body)"
          />

          {/* collar */}
          <path d="M -14 16 L 0 26 L 14 16" fill="none" stroke="#c9b8ff" strokeWidth="2" />

          {/* music-note pin */}
          <g transform="translate(26 -6)" fill="#c9b8ff">
            <circle cx="0" cy="0" r="2.4" />
            <circle cx="6" cy="2" r="2.4" />
            <path d="M 2.4 -2 L 2.4 -12 L 8.4 -9 L 8.4 0" fill="none" stroke="#c9b8ff" strokeWidth="1.6" />
          </g>

          {/* brows */}
          <g
            stroke="#241a45"
            strokeWidth="2.6"
            strokeLinecap="round"
            transform={`translate(0 ${face.browOffset}) rotate(${face.browRotate})`}
          >
            <path d="M -20 -20 L -9 -23" />
            <path d="M 20 -20 L 9 -23" />
          </g>

          {/* eyes */}
          <g transform="translate(-10 2)">
            <path d={eyePath} fill={eyeFill} stroke={eyeStroke} strokeWidth="2" strokeLinecap="round" />
          </g>
          <g transform="translate(10 2)">
            <path d={eyePath} fill={eyeFill} stroke={eyeStroke} strokeWidth="2" strokeLinecap="round" />
          </g>

          {/* mouth */}
          <g transform="translate(0 20)">
            <path
              d={mouthShape}
              fill={mouthFilled ? '#2b2150' : 'none'}
              stroke="#2b2150"
              strokeWidth="2.4"
              strokeLinecap="round"
              transform={`scale(1 ${mouthScale})`}
            />
          </g>
        </svg>
      </div>
      <div className="avatar-emotion-label">{EMOTION_LABELS[emotion] || emotion}</div>
    </div>
  );
};