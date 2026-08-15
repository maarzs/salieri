import React from 'react';

// Using static imports for Vite as suggested
import maleNeutral from '../assets/mascots/male/neutral.png';
import femaleNeutral from '../assets/mascots/female/neutral.png';

const MASCOT_SPRITES: Record<string, Record<string, string>> = {
  male: { neutral: maleNeutral },
  female: { neutral: femaleNeutral },
};

interface MascotProps {
  character: 'male' | 'female';
  emotion: string;
  isSpeaking: boolean;
  onClick: () => void;
  size?: 'normal' | 'small';
}

export const Mascot: React.FC<MascotProps> = ({
  character,
  emotion,
  isSpeaking,
  onClick,
  size = 'normal'
}) => {
  const spriteSrc = MASCOT_SPRITES[character]?.[emotion] || MASCOT_SPRITES[character]?.neutral;
  
  const sizeClass = size === 'small' ? 'mascot--small' : '';
  const stateClass = isSpeaking ? 'mascot--speaking' : 'mascot--idle mascot--breathing';
  const emotionClass = `mascot--${emotion}`;
  
  return (
    <div 
      className={`mascot ${sizeClass} ${stateClass} ${emotionClass}`.trim()} 
      onClick={onClick}
    >
      {isSpeaking && <div className="mascot__glow" />}
      <img src={spriteSrc} alt={`${character} mascot`} className="mascot__image" draggable={false} />
    </div>
  );
};
