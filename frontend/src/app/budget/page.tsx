import React from 'react';

export default async function BudgetPage() {
    let usage = [];
    try {
        const res = await fetch('http://nl-api-gateway:8000/api/v1/budget', { cache: 'no-store' });
        if (res.ok) {
            const data = await res.json();
            usage = data.usage || [];
        }
    } catch (e) {
        console.error("Failed to fetch budget", e);
    }

    const limits: Record<string, number> = {
        'GeminiProvider': 500,
        'GroqProvider': 1000,
        'OpenRouterProvider': 200,
        'MistralProvider': 200
    };

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold mb-6">Quota & Budget Dashboard</h1>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {Object.keys(limits).map(provider => {
                    const row = usage.find((u: any) => u.provider === provider);
                    const used = row ? row.request_count : 0;
                    const limit = limits[provider];
                    const pct = Math.min(100, Math.round((used / limit) * 100));
                    
                    let colorClass = 'bg-green-500';
                    if (pct >= 70) colorClass = 'bg-yellow-500';
                    if (pct >= 90) colorClass = 'bg-red-500';

                    return (
                        <div key={provider} className="bg-white rounded shadow p-6 border">
                            <h2 className="text-xl font-semibold mb-2">{provider}</h2>
                            <div className="mb-4">
                                <span className="text-gray-600">Used today:</span> {used} / {limit} ({pct}%)
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-4">
                                <div className={h-4 rounded-full } style={{ width: pct + '%' }}></div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
