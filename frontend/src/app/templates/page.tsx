import React from 'react';
import Link from 'next/link';

export default async function TemplatesPage() {
    let templates = [];
    try {
        const res = await fetch('http://nl-api-gateway:8000/api/v1/templates', { cache: 'no-store' });
        if (res.ok) {
            const data = await res.json();
            templates = data.templates || [];
        }
    } catch (e) {
        console.error("Failed to fetch templates", e);
    }

    return (
        <div className="p-8 max-w-5xl mx-auto">
            <h1 className="text-3xl font-bold mb-6">Automation Templates</h1>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {templates.map((tpl: any) => (
                    <div key={tpl.id} className="bg-white rounded shadow p-6 border flex flex-col">
                        <h2 className="text-xl font-semibold mb-2">{tpl.title}</h2>
                        <p className="text-gray-600 mb-4 flex-grow">{tpl.description}</p>
                        <div className="text-sm font-mono bg-gray-50 p-2 rounded mb-4">
                            {tpl.raw_text_template}
                        </div>
                        <Link href={/?template=} className="bg-blue-600 text-white text-center py-2 px-4 rounded hover:bg-blue-700 transition">
                            Use this
                        </Link>
                    </div>
                ))}
            </div>
        </div>
    );
}
