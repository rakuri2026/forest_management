import React, { useState } from 'react';

interface HelpTooltipProps {
  title?: string;
  children: React.ReactNode;
  position?: 'top' | 'right' | 'bottom' | 'left';
  helpText: string;
}

const HelpTooltip: React.FC<HelpTooltipProps> = ({
  children,
  position = 'right',
  helpText,
}) => {
  const [isVisible, setIsVisible] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  };

  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-gray-700 border-l-transparent border-r-transparent border-b-transparent',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-gray-700 border-t-transparent border-b-transparent border-l-transparent',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-gray-700 border-l-transparent border-r-transparent border-t-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-gray-700 border-t-transparent border-b-transparent border-r-transparent',
  };

  return (
    <div className="relative inline-block">
      {children}
      <button
        type="button"
        onClick={() => setIsVisible(!isVisible)}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        className="ml-1 inline-flex items-center justify-center w-5 h-5 text-gray-400 hover:text-gray-600 rounded-full border border-gray-300 hover:border-gray-400 transition-colors"
        aria-label="Help"
      >
        <span className="text-xs font-bold">?</span>
      </button>

      {isVisible && (
        <div
          className={`absolute z-50 w-72 p-3 text-sm bg-gray-800 text-white rounded-lg shadow-lg ${positionClasses[position]}`}
        >
          <p className="leading-relaxed">{helpText}</p>
          <div
            className={`absolute w-0 h-0 border-4 ${arrowClasses[position]}`}
          />
        </div>
      )}
    </div>
  );
};

export default HelpTooltip;

// Contextual help texts in Nepali (with English fallbacks)
export const helpTexts = {
  gpsPoints: {
    title: 'GPS Points',
    text: 'GPS अंकहरू वैकल्पिक हुन्। यदि तपाईंसँग तपाईंको वन क्षेत्रको GPS निर्देशांकहरू छन् भने, तिनीहरूलाई यहाँ प्रविष्टि गर्न सक्नुहुन्छ। यो नक्शामा सीमाना कोर्न मद्दत गर्दछ।\n\nGPS coordinates are optional. If you have GPS coordinates for your forest area, you can enter them here to help with boundary drawing.',
  },
  islands: {
    title: 'टापुहरू',
    text: 'टापु भनेको तपाईंको वन क्षेत्रको अलग-अलग भाग हो। यदि तपाईंको वन एउटै क्षेत्रमा छ भने, यो एउटै टापु हुनेछ। धेरै छुट्टै क्षेत्रहरू भएमा, प्रत्येकलाई छुट्टै टापुको रूपमा थप्नुहोस्।\n\nAn island is a separate part of your forest area. If your forest is in one continuous area, it will be one island. If there are multiple separate areas, add each as a separate island.',
  },
  addIsland: {
    title: 'Add Island Button',
    text: 'नयाँ टापु थप्नको लागि: 1) यो बटनमा क्लिक गर्नुहोस्, 2) नक्शामा बहुभुज आइकनमा क्लिक गर्नुहोस्, 3) नक्शामा क्लिक गरेर शीर्षकहरू थप्नुहोस्, 4) बहुभुज पूरा गर्न डबल-क्लिक गर्नुहोस्।\n\nTo add a new island: 1) Click this button, 2) Click the polygon icon on the map, 3) Click on the map to add vertices, 4) Double-click to complete the polygon.',
  },
  blocks: {
    title: 'ब्लकहरू',
    text: 'ब्लक भनेको वन प्रबन्धनको एकाइ हो। पूर्वनिर्धारित रूपमा, प्रत्येक टापु एउटा ब्लक बन्छ। तपाईं ब्लकहरूको नाम परिवर्तन गर्न सक्नुहुन्छ वा एउटा ब्लकलाई धेरै भागमा विभाजन गर्न सक्नुहुन्छ।\n\nA block is a forest management unit. By default, each island becomes one block. You can rename blocks or split one block into multiple sections.',
  },
  subAreas: {
    title: 'उप-क्षेत्रहरू',
    text: 'उप-क्षेत्रहरू तपाईंको वन भित्रका विशेष क्षेत्रहरू हुन्। जस्तै: संरक्षित क्षेत्र, रोपण क्षेत्र, धार्मिक स्थल, आदि। निजी जमिनलाई "निजी जमिन (बाहिर गरिएको)" को रूपमा चिन्नुहोस्।\n\nSub-areas are special zones within your forest, such as: protected zones, plantation areas, religious sites, etc. Mark private lands as "Private Land (Excluded)".',
  },
  saveDraft: {
    title: 'Save Draft',
    text: 'यदि तपाईंले काम रोक्नु पर्छ भने, "Save Draft" मा क्लिक गर्नुहोस्। तपाईंले पछि काम जारी राख्न सक्नुहुनेछ। फर्कदा, "My Uploads" बाट "Resume Draft" मा क्लिक गर्नुहोस्।\n\nIf you need to stop work, click "Save Draft". You can continue your work later. When you return, click "Resume Draft" from "My Uploads".',
  },
  saveAndNext: {
    title: 'Save and Continue',
    text: 'समीक्षा पृष्ठमा जान "Save →" मा क्लिक गर्नुहोस्। तपाईंले सबै ब्लकहरू र उप-क्षेत्रहरू समीक्षा गर्न सक्नुहुनेछ, त्यसपछि वन बचत गर्न सक्नुहुनेछ।\n\nClick "Save →" to go to the review page. You can review all blocks and sub-areas, then save the forest.',
  },
  drawPolygon: {
    title: 'Drawing Polygons',
    text: 'बहुभुज कोर्नको लागि: 1) पहिले "+ Add Island" मा क्लिक गर्नुहोस्, 2) नक्शा टूलबारमा बहुभुज आइकनमा क्लिक गर्नुहोस्, 3) कोण थप्न नक्शामा क्लिक गर्नुहोस्, 4) पूरा गर्न डबल-क्लिक गर्नुहोस्।\n\nTo draw a polygon: 1) First click "+ Add Island", 2) Click the polygon icon in the map toolbar, 3) Click on the map to add corners, 4) Double-click to complete.',
  },
  protectedZone: {
    title: 'संरक्षित क्षेत्र',
    text: 'संरक्षित क्षेत्र भनेको विशेष संरक्षण आवश्यकता भएको क्षेत्र हो। यसमा संवेदनशील वन, जैविक विविधता सम्पन्न क्षेत्र, वा संरक्षित प्रजातिहरूको बासस्थान समावेश हुन सक्छ।\n\nProtected zone is an area with special conservation needs. This may include sensitive forests, biodiversity-rich areas, or habitats of protected species.',
  },
  plantationArea: {
    title: 'रोपण क्षेत्र',
    text: 'रोपण क्षेत्र भनेको नयाँ वृक्ष रोप्नको लागि निर्दिष्ट क्षेत्र हो। यो क्षेत्र वन स्थापना र सामुदायिक वृक्षारोपण कार्यक्रमहरूको लागि प्रयोग गरिन्छ।\n\nPlantation area is an area designated for planting new trees. This area is used for forest establishment and community tree planting programs.',
  },
  privateLand: {
    title: 'निजी जमिन',
    text: 'निजी जमिन भनेको वन क्षेत्र भित्रको तर समुदाय वनमा नसमेटिएको निजी स्वामित्वमा रहेको जमिन हो। यो क्षेत्र वन गणनाबाट बाहिर गरिनेछ।\n\nPrivate land is land within the forest area but privately owned and not part of the community forest. This area will be excluded from forest calculations.',
  },
  encroachedArea: {
    title: 'अतीक्रमीत क्षेत्र',
    text: 'अतीक्रमीत क्षेत्र भनेको वन क्षेत्र मानिसहरूले अवैध रूपमा कब्जा गरेको क्षेत्र हो। यो क्षेत्र वन प्रबन्धन योजनामा निगरानीको लागि चिन्हित गरिन्छ।\n\nEncroached area is forest land that has been illegally occupied by people. This area is marked for monitoring in the forest management plan.',
  },
};
