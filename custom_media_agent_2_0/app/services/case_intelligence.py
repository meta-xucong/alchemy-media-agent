from __future__ import annotations

import re
from collections import Counter

from app.config import settings
from app.repositories import repository
from app.schemas import CaseProfile, PromptCase, PromptCaseSummary, SearchPromptCasesRequest, SearchPromptCasesResponse
from app.services.bootstrap import bootstrap_v2_repository
from app.services.visual_signals import build_case_visual_signals


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
MIN_FREE_TEXT_RELEVANCE_SCORE = 0.5
_CASE_BASE_TEXT_CACHE: dict[tuple[str, str], str] = {}
_CASE_FEATURE_CACHE: dict[tuple[str, str], set[str]] = {}
_CASE_PROFILE_CACHE: dict[tuple[str, str, str, str | None], CaseProfile] = {}
_CASE_SEARCH_TEXT_CACHE: dict[tuple[str, str, str, str | None], str] = {}
CORE_SUBJECT_FEATURES = {
    "subject.perfume",
    "subject.skincare",
    "subject.watch",
    "subject.food_drink",
    "subject.pet",
    "subject.jewelry",
    "subject.footwear",
    "subject.automotive",
    "subject.fashion",
    "subject.bag_accessory",
    "subject.electronics",
    "subject.furniture",
    "subject.plant_flower",
    "subject.travel_city",
    "subject.finance",
    "subject.education",
    "subject.music",
    "subject.game_scifi",
    "subject.wedding",
    "subject.kids",
}
CORE_SUBJECT_EQUIVALENTS = {
    "subject.perfume": {"subject.perfume", "subject.skincare", "subject.bottle"},
}

GENERIC_QUERY_TOKENS = {
    "ad",
    "advertising",
    "campaign",
    "commercial",
    "ecommerce",
    "hero",
    "image",
    "listing",
    "marketplace",
    "product",
    "visual",
}

QUERY_EXPANSIONS = {
    "电商": ["ecommerce", "marketplace", "product", "listing"],
    "主图": ["ecommerce", "product", "listing", "hero"],
    "产品": ["product", "commercial", "packaging"],
    "香水": ["perfume", "bottle", "luxury", "product"],
    "护肤": ["skincare", "beauty", "product"],
    "食物": ["food", "cuisine", "dish", "meal", "snack", "product"],
    "美食": ["food", "cuisine", "dish", "meal", "restaurant"],
    "菜品": ["food", "cuisine", "dish", "meal", "plate"],
    "甜品": ["dessert", "cake", "pastry", "food"],
    "水果": ["fruit", "food", "fresh"],
    "饮料": ["drink", "beverage", "product"],
    "海报": ["poster", "campaign", "typography"],
    "广告": ["ad", "advertising", "campaign", "commercial"],
    "奢华": ["luxury", "premium", "high-end"],
    "高级": ["premium", "luxury", "commercial"],
    "黑金": ["black", "gold", "luxury", "premium"],
    "玻璃瓶": ["glass", "bottle", "perfume", "product"],
    "极简": ["minimal", "clean"],
    "干净": ["clean", "minimal"],
    "电影": ["cinematic", "film"],
    "人像": ["portrait", "face", "headshot"],
    "角色": ["character", "mascot"],
    "赛博": ["cyberpunk", "neon", "futuristic"],
    "复古": ["retro", "vintage"],
    "插画": ["illustration", "illustrated"],
    "界面": ["ui", "dashboard", "interface"],
    "仪表盘": ["dashboard", "ui", "interface"],
    "科技": ["technology", "tech", "futuristic", "interface"],
    "珠宝": ["jewelry", "ring", "necklace", "luxury", "product"],
    "首饰": ["jewelry", "ring", "necklace", "accessory"],
    "鞋": ["shoe", "sneaker", "footwear", "product"],
    "运动": ["sport", "fitness", "athletic", "energy"],
    "汽车": ["car", "automotive", "vehicle", "campaign"],
    "家居": ["interior", "home", "furniture", "lifestyle"],
    "建筑": ["architecture", "building", "real estate"],
    "医疗": ["medical", "healthcare", "clinical", "clean"],
    "美妆": ["beauty", "cosmetic", "skincare", "product"],
    "包装": ["packaging", "product", "label"],
}

QUERY_EXPANSIONS.update(
    {
        "宠物": ["pet", "cat", "dog", "animal", "poster", "lifestyle"],
        "猫": ["cat", "pet", "animal"],
        "狗": ["dog", "pet", "animal"],
        "家具": ["furniture", "sofa", "chair", "interior", "home"],
        "室内": ["interior", "home", "room"],
        "沙发": ["sofa", "furniture", "interior"],
        "椅子": ["chair", "furniture", "interior"],
        "灯具": ["lamp", "lighting fixture", "furniture", "interior"],
        "服装": ["fashion", "apparel", "clothing", "fabric", "product"],
        "衣服": ["fashion", "apparel", "clothing", "fabric"],
        "穿搭": ["fashion", "outfit", "editorial", "lookbook"],
        "卫衣": ["hoodie", "fashion", "apparel"],
        "裙子": ["dress", "fashion", "apparel"],
        "包袋": ["bag", "handbag", "accessory", "fashion", "product"],
        "手袋": ["handbag", "bag", "accessory", "fashion", "product"],
        "旅行": ["travel", "city", "map", "landmark", "poster"],
        "旅游": ["travel", "city", "map", "landmark", "poster"],
        "城市": ["city", "urban", "map", "travel"],
        "地图": ["map", "city", "travel", "illustration"],
        "景点": ["landmark", "travel", "city"],
        "金融": ["finance", "bank", "fintech", "insurance", "dashboard"],
        "银行": ["bank", "finance", "fintech", "app", "ui"],
        "理财": ["finance", "wealth", "investment", "bank"],
        "保险": ["insurance", "finance", "healthcare"],
        "教育": ["education", "course", "school", "learning", "poster"],
        "课程": ["course", "education", "learning"],
        "学校": ["school", "education", "campus"],
        "学习": ["learning", "education", "student"],
        "音乐": ["music", "concert", "album", "poster"],
        "乐队": ["band", "music", "concert", "poster"],
        "演唱会": ["concert", "music", "stage", "poster"],
        "唱片": ["album", "record", "music", "cover"],
        "游戏": ["game", "gaming", "esports", "sci-fi", "character"],
        "电竞": ["esports", "gaming", "neon", "poster"],
        "机甲": ["mecha", "robot", "sci-fi", "character"],
        "科幻": ["sci-fi", "futuristic", "space", "technology"],
        "婚礼": ["wedding", "couple", "romantic", "poster"],
        "情侣": ["couple", "romantic", "portrait", "lifestyle"],
        "儿童": ["kids", "children", "toy", "playful"],
        "母婴": ["baby", "kids", "family", "soft"],
        "手机": ["phone", "smartphone", "device", "technology", "product"],
        "耳机": ["headphone", "earbud", "device", "technology", "product"],
        "电脑": ["computer", "laptop", "device", "technology"],
        "数码": ["device", "electronics", "technology", "product"],
        "花": ["flower", "floral", "plant", "nature"],
        "植物": ["plant", "botanical", "nature", "green"],
        "森林": ["forest", "nature", "green", "landscape"],
        "海边": ["beach", "ocean", "travel", "landscape"],
        "山": ["mountain", "nature", "landscape", "travel"],
        "春节": ["chinese new year", "spring festival", "red", "festive"],
        "圣诞": ["christmas", "holiday", "festive", "winter"],
        "新年": ["new year", "holiday", "festive"],
        "信息图": ["infographic", "diagram", "layout", "typography"],
        "对比": ["comparison", "before after", "layout"],
        "故事板": ["storyboard", "sequence", "comic", "panels"],
        "3D": ["3d", "render", "cgi"],
        "可爱": ["cute", "playful", "soft"],
        "水彩": ["watercolor", "illustration", "soft"],
        "国风": ["chinese", "oriental", "ink", "traditional"],
    }
)

FEATURE_RULES = {
    "subject.perfume": {
        "query": ["香水", "香氛", "perfume", "fragrance"],
        "case": ["perfume", "parfum", "fragrance", "scent"],
    },
    "subject.skincare": {
        "query": ["护肤", "精华", "面霜", "skincare", "serum"],
        "case": ["skincare", "serum", "cream", "cosmetic"],
    },
    "subject.bottle": {
        "query": ["瓶", "瓶身", "玻璃瓶", "bottle"],
        "case": ["bottle", "flacon", "vessel"],
    },
    "subject.watch": {
        "query": ["手表", "腕表", "watch", "chronograph"],
        "case": ["watch", "chronograph", "timepiece"],
    },
    "subject.food_drink": {
        "query": ["食物", "食品", "美食", "菜品", "餐饮", "甜品", "水果", "饮料", "咖啡", "酒", "茶", "food", "dish", "meal", "drink", "beverage"],
        "case": [
            "食物",
            "食品",
            "美食",
            "菜品",
            "food",
            "dish",
            "meal",
            "cuisine",
            "beverage",
            "coffee",
            "tea",
            "snack",
            "dessert",
            "cake",
            "pastry",
            "fruit",
            "grain powder",
            "bowl",
        ],
    },
    "subject.person": {
        "query": ["人像", "人物", "真人", "portrait", "person"],
        "case": ["portrait", "person", "woman", "man", "model", "founder"],
    },
    "subject.character": {
        "query": ["角色", "IP", "吉祥物", "character", "mascot"],
        "case": ["character", "mascot", "full-body", "pose"],
    },
    "subject.interface": {
        "query": ["界面", "仪表盘", "后台", "app", "ui", "dashboard"],
        "case": ["ui", "dashboard", "interface", "app", "saas"],
    },
    "subject.jewelry": {
        "query": ["珠宝", "首饰", "戒指", "项链", "jewelry"],
        "case": ["jewelry", "ring", "necklace", "bracelet", "gemstone", "diamond"],
    },
    "subject.footwear": {
        "query": ["鞋", "球鞋", "运动鞋", "sneaker", "shoe"],
        "case": ["shoe", "sneaker", "footwear", "trainer"],
    },
    "subject.automotive": {
        "query": ["汽车", "车", "automotive", "vehicle"],
        "case": ["car", "automotive", "vehicle", "sedan", "suv"],
    },
    "subject.architecture": {
        "query": ["建筑", "楼盘", "房产", "architecture", "real estate"],
        "case": ["architecture", "building", "real estate", "interior"],
    },
    "material.glass": {
        "query": ["玻璃", "透明", "水晶", "glass", "crystal"],
        "case": ["glass", "transparent", "crystal", "refraction"],
    },
    "material.metal": {
        "query": ["金属", "金色金属", "metal", "metallic"],
        "case": ["metal", "metallic", "brushed", "chrome"],
    },
    "material.fabric": {
        "query": ["织物", "布料", "服装", "fabric", "textile"],
        "case": ["fabric", "textile", "cloth", "woven", "silk"],
    },
    "color.black": {
        "query": ["黑", "黑色", "黑金", "black"],
        "case": ["black", "charcoal", "dark"],
    },
    "color.gold": {
        "query": ["金", "金色", "黑金", "gold"],
        "case": ["gold", "golden", "brass", "amber"],
    },
    "color.green": {
        "query": ["绿色", "墨绿", "emerald", "green"],
        "case": ["green", "emerald", "forest"],
    },
    "color.blue": {
        "query": ["蓝色", "科技蓝", "blue"],
        "case": ["blue", "cyan", "azure"],
    },
    "color.pink": {
        "query": ["粉色", "少女", "pink"],
        "case": ["pink", "rose", "blush"],
    },
    "tone.luxury": {
        "query": ["奢华", "高级", "高端", "质感", "luxury", "premium"],
        "case": ["luxury", "luxurious", "premium", "high-end", "opulence", "elegance"],
    },
    "tone.minimal": {
        "query": ["极简", "干净", "留白", "minimal", "clean"],
        "case": ["minimal", "clean", "negative space", "uncluttered"],
    },
    "tone.cinematic": {
        "query": ["电影", "戏剧", "cinematic", "film"],
        "case": ["cinematic", "film", "dramatic", "moody"],
    },
    "tone.cyberpunk": {
        "query": ["赛博", "霓虹", "未来", "cyberpunk", "neon", "futuristic"],
        "case": ["cyberpunk", "neon", "futuristic", "sci-fi"],
    },
    "tone.retro": {
        "query": ["复古", "怀旧", "retro", "vintage"],
        "case": ["retro", "vintage", "nostalgic"],
    },
    "tone.technology": {
        "query": ["科技", "未来", "智能", "technology", "futuristic"],
        "case": ["technology", "tech", "futuristic", "holographic", "interface"],
    },
    "tone.medical_clean": {
        "query": ["医疗", "健康", "临床", "medical", "healthcare"],
        "case": ["medical", "healthcare", "clinical", "sterile"],
    },
    "style.illustration": {
        "query": ["插画", "手绘", "illustration", "illustrated"],
        "case": ["illustration", "illustrated", "hand-drawn", "drawing"],
    },
    "lighting.studio": {
        "query": ["棚拍", "影棚", "布光", "studio lighting"],
        "case": ["studio", "softbox", "rim light", "key light", "controlled lighting"],
    },
    "lighting.neon": {
        "query": ["霓虹", "neon"],
        "case": ["neon", "glow", "glowing"],
    },
    "lighting.natural": {
        "query": ["自然光", "阳光", "日光", "natural light", "sunlight"],
        "case": ["natural light", "sunlight", "daylight"],
    },
    "composition.hero": {
        "query": ["主图", "头图", "中心构图", "hero", "main image"],
        "case": ["hero", "centered", "main image", "centered composition"],
    },
    "composition.flatlay": {
        "query": ["俯拍", "平铺", "flat lay", "flatlay"],
        "case": ["flat lay", "flatlay", "top-down"],
    },
    "composition.typography_safe": {
        "query": ["留字", "文案区", "标题", "typography"],
        "case": ["typography", "headline", "copy space", "negative space"],
    },
    "use.ecommerce": {
        "query": ["电商", "商品图", "详情页", "商城", "ecommerce", "marketplace"],
        "case": ["ecommerce", "marketplace", "product listing", "commercial product"],
    },
    "use.poster": {
        "query": ["海报", "poster"],
        "case": ["poster", "headline", "typography-safe"],
    },
    "use.ad": {
        "query": ["广告", "营销", "campaign", "ad", "advertising"],
        "case": ["advertising", "campaign", "commercial", "ad creative"],
    },
    "use.social": {
        "query": ["社媒", "小红书", "instagram", "social"],
        "case": ["social media", "instagram", "story"],
    },
    "use.packaging": {
        "query": ["包装", "包装设计", "packaging"],
        "case": ["packaging", "label", "box", "package"],
    },
}

FEATURE_RULES.update(
    {
        "subject.pet": {
            "query": ["宠物", "猫", "狗", "pet", "cat", "dog"],
            "case": ["pet", "cat", "dog", "puppy", "kitten", "animal companion"],
        },
        "subject.fashion": {
            "query": ["服装", "衣服", "穿搭", "卫衣", "裙子", "fashion", "apparel", "clothing", "outfit"],
            "case": ["fashion", "apparel", "clothing", "outfit", "lookbook", "hoodie", "dress", "garment"],
        },
        "subject.bag_accessory": {
            "query": ["包袋", "手袋", "女包", "背包", "accessory", "handbag", "bag"],
            "case": ["handbag", "bag", "accessory", "purse", "tote"],
        },
        "subject.electronics": {
            "query": ["手机", "耳机", "电脑", "数码", "电子产品", "phone", "headphone", "laptop", "device"],
            "case": ["smartphone", "phone", "headphone", "earbud", "laptop", "computer", "device", "electronics"],
        },
    "subject.furniture": {
        "query": ["家具", "沙发", "椅子", "灯具", "furniture", "sofa", "chair", "lamp"],
        "case": ["furniture", "sofa", "couch", "armchair", "chair", "lamp", "lighting fixture", "cabinet"],
        },
        "subject.interior": {
            "query": ["室内", "家居", "空间", "interior", "home", "room"],
            "case": ["interior", "home", "room", "living room", "bedroom", "workspace"],
        },
        "subject.plant_flower": {
            "query": ["花", "植物", "森林", "自然", "flower", "plant", "nature"],
            "case": ["flower", "floral", "plant", "botanical", "forest", "nature", "garden"],
        },
        "subject.travel_city": {
            "query": ["旅行", "旅游", "城市", "地图", "景点", "travel", "city", "map", "landmark"],
            "case": ["travel", "city", "urban", "map", "landmark", "tourism", "destination"],
        },
    "subject.finance": {
        "query": ["金融", "银行", "理财", "保险", "finance", "bank", "fintech", "insurance"],
        "case": ["finance", "bank", "banking", "fintech", "insurance"],
        },
        "subject.education": {
            "query": ["教育", "课程", "学校", "学习", "education", "course", "school", "learning"],
            "case": ["education", "course", "school", "learning", "student", "classroom", "academy"],
        },
        "subject.music": {
            "query": ["音乐", "乐队", "演唱会", "唱片", "music", "concert", "album", "band"],
            "case": ["music", "concert", "album", "record", "band", "stage", "playlist"],
        },
        "subject.game_scifi": {
            "query": ["游戏", "电竞", "机甲", "科幻", "game", "gaming", "esports", "mecha", "sci-fi"],
            "case": ["game", "gaming", "esports", "mecha", "robot", "sci-fi", "space", "cyber"],
        },
        "subject.wedding": {
            "query": ["婚礼", "情侣", "wedding", "couple", "romantic"],
            "case": ["wedding", "couple", "bride", "groom", "romantic", "ceremony"],
        },
        "subject.kids": {
            "query": ["儿童", "孩子", "母婴", "宝宝", "kids", "children", "baby"],
            "case": ["kids", "children", "child", "baby", "toy", "family"],
        },
        "material.wood": {
            "query": ["木质", "木头", "原木", "wood", "wooden"],
            "case": ["wood", "wooden", "oak", "walnut", "timber"],
        },
        "material.paper": {
            "query": ["纸", "纸张", "书页", "paper"],
            "case": ["paper", "cardstock", "book", "page", "folded"],
        },
        "material.ceramic": {
            "query": ["陶瓷", "瓷器", "ceramic", "porcelain"],
            "case": ["ceramic", "porcelain", "clay", "glazed"],
        },
        "material.leather": {
            "query": ["皮革", "真皮", "leather"],
            "case": ["leather", "suede", "grain leather"],
        },
        "material.plastic": {
            "query": ["塑料", "亚克力", "plastic", "acrylic"],
            "case": ["plastic", "acrylic", "resin", "polycarbonate"],
        },
        "material.water_liquid": {
            "query": ["水", "液体", "水花", "liquid", "water", "splash"],
            "case": ["water", "liquid", "splash", "droplet", "fluid"],
        },
        "color.red": {
            "query": ["红", "红色", "春节", "red"],
            "case": ["red", "crimson", "scarlet", "ruby"],
        },
        "color.white": {
            "query": ["白", "白色", "纯白", "white"],
            "case": ["white", "ivory", "cream", "pearl"],
        },
        "color.silver": {
            "query": ["银", "银色", "silver"],
            "case": ["silver", "chrome", "platinum"],
        },
        "color.purple": {
            "query": ["紫", "紫色", "purple"],
            "case": ["purple", "violet", "lavender"],
        },
        "tone.cute": {
            "query": ["可爱", "萌", "童趣", "cute", "playful"],
            "case": ["cute", "playful", "whimsical", "adorable", "soft"],
        },
        "tone.elegant": {
            "query": ["优雅", "精致", "典雅", "elegant", "refined"],
            "case": ["elegant", "refined", "graceful", "sophisticated"],
        },
        "tone.dark": {
            "query": ["暗黑", "黑暗", "深色", "dark", "moody"],
            "case": ["dark", "moody", "low-key", "shadowy"],
        },
        "tone.anime": {
            "query": ["动漫", "二次元", "anime", "manga"],
            "case": ["anime", "manga", "cel-shaded", "comic"],
        },
        "tone.watercolor": {
            "query": ["水彩", "watercolor"],
            "case": ["watercolor", "wash", "painted"],
        },
        "tone.three_d": {
            "query": ["3D", "三维", "立体", "3d", "cgi", "render"],
            "case": ["3d", "cgi", "render", "octane", "blender"],
        },
        "tone.chinese_oriental": {
            "query": ["国风", "中式", "东方", "水墨", "chinese", "oriental", "ink"],
            "case": ["chinese", "oriental", "ink", "traditional", "calligraphy"],
        },
        "composition.closeup": {
            "query": ["特写", "近景", "closeup", "close-up", "macro"],
            "case": ["closeup", "close-up", "macro", "detail shot"],
        },
        "composition.collage": {
            "query": ["拼贴", "拼版", "collage"],
            "case": ["collage", "montage", "cutout", "mixed layout"],
        },
        "composition.infographic": {
            "query": ["信息图", "图解", "infographic", "diagram"],
            "case": ["infographic", "diagram", "annotated", "data visualization"],
        },
        "composition.storyboard": {
            "query": ["故事板", "分镜", "storyboard", "sequence"],
            "case": ["storyboard", "sequence", "panels", "comic strip"],
        },
        "use.travel": {
            "query": ["旅行", "旅游", "城市宣传", "travel", "tourism"],
            "case": ["travel", "tourism", "destination", "city guide"],
        },
        "use.fashion": {
            "query": ["服装", "穿搭", "时尚广告", "fashion", "lookbook"],
            "case": ["fashion", "lookbook", "editorial fashion", "apparel campaign"],
        },
    "use.finance": {
        "query": ["金融", "银行", "理财", "保险", "finance", "banking", "fintech"],
        "case": ["finance", "banking", "fintech", "insurance"],
        },
        "use.education": {
            "query": ["教育", "课程", "学习", "education", "course", "learning"],
            "case": ["education", "course", "learning", "school"],
        },
        "use.game": {
            "query": ["游戏", "电竞", "game", "gaming", "esports"],
            "case": ["game", "gaming", "esports", "quest", "level"],
        },
        "use.infographic": {
            "query": ["信息图", "图解", "infographic"],
            "case": ["infographic", "diagram", "explainer"],
        },
        "use.storyboard": {
            "query": ["故事板", "分镜", "storyboard"],
            "case": ["storyboard", "sequence", "panels"],
        },
        "use.real_estate": {
            "query": ["房产", "楼盘", "地产", "real estate", "property"],
            "case": ["real estate", "property", "architecture", "interior"],
        },
    }
)

FEATURE_LABELS_ZH = {
    "subject.perfume": "香水香氛",
    "subject.skincare": "护肤美妆",
    "subject.bottle": "瓶身产品",
    "subject.watch": "腕表",
    "subject.food_drink": "食品饮料",
    "subject.person": "人物人像",
    "subject.character": "角色形象",
    "subject.interface": "界面仪表盘",
    "subject.jewelry": "珠宝首饰",
    "subject.footwear": "鞋履",
    "subject.automotive": "汽车",
    "subject.architecture": "建筑空间",
    "material.glass": "玻璃材质",
    "material.metal": "金属材质",
    "material.fabric": "织物材质",
    "color.black": "黑色",
    "color.gold": "金色",
    "color.green": "绿色",
    "color.blue": "蓝色",
    "color.pink": "粉色",
    "tone.luxury": "高级奢华",
    "tone.minimal": "极简干净",
    "tone.cinematic": "电影感",
    "tone.cyberpunk": "赛博霓虹",
    "tone.retro": "复古",
    "tone.technology": "科技未来",
    "tone.medical_clean": "医疗洁净",
    "style.illustration": "插画手绘",
    "lighting.studio": "棚拍布光",
    "lighting.neon": "霓虹发光",
    "lighting.natural": "自然光",
    "composition.hero": "主图构图",
    "composition.flatlay": "俯拍平铺",
    "composition.typography_safe": "文案留白",
    "use.ecommerce": "电商用途",
    "use.poster": "海报用途",
    "use.ad": "广告用途",
    "use.social": "社媒用途",
    "use.packaging": "包装用途",
}

FEATURE_LABELS_ZH.update(
    {
        "subject.pet": "宠物动物",
        "subject.fashion": "服装时尚",
        "subject.bag_accessory": "包袋配饰",
        "subject.electronics": "数码电子",
        "subject.furniture": "家具产品",
        "subject.interior": "室内家居",
        "subject.plant_flower": "花植自然",
        "subject.travel_city": "旅行城市",
        "subject.finance": "金融银行",
        "subject.education": "教育课程",
        "subject.music": "音乐演出",
        "subject.game_scifi": "游戏科幻",
        "subject.wedding": "婚礼情侣",
        "subject.kids": "儿童母婴",
        "material.wood": "木质材质",
        "material.paper": "纸张材质",
        "material.ceramic": "陶瓷材质",
        "material.leather": "皮革材质",
        "material.plastic": "塑料亚克力",
        "material.water_liquid": "水与液体",
        "color.red": "红色",
        "color.white": "白色",
        "color.silver": "银色",
        "color.purple": "紫色",
        "tone.cute": "可爱童趣",
        "tone.elegant": "优雅精致",
        "tone.dark": "暗黑氛围",
        "tone.anime": "动漫二次元",
        "tone.watercolor": "水彩质感",
        "tone.three_d": "3D 渲染",
        "tone.chinese_oriental": "国风东方",
        "composition.closeup": "近景特写",
        "composition.collage": "拼贴排版",
        "composition.infographic": "信息图构图",
        "composition.storyboard": "故事板分镜",
        "use.travel": "旅行宣传",
        "use.fashion": "时尚用途",
        "use.finance": "金融用途",
        "use.education": "教育用途",
        "use.game": "游戏用途",
        "use.infographic": "信息图用途",
        "use.storyboard": "故事板用途",
        "use.real_estate": "房产空间用途",
    }
)


def search_prompt_cases(request: SearchPromptCasesRequest) -> SearchPromptCasesResponse:
    bootstrap_v2_repository(seed_cases=True)
    cases = repository.list_cases(active_only=True)
    scored: list[tuple[float, str, PromptCase]] = []
    has_free_text_query = bool(request.query_text.strip())
    for case in cases:
        if request.category_filters and case.category not in request.category_filters:
            continue
        if request.style_filters and not set(request.style_filters).intersection(case.style_tags):
            continue
        if request.use_case_filters and not set(request.use_case_filters).intersection(case.use_case_tags):
            continue
        if _excluded_by_risk(request.risk_filters, case):
            continue
        score, reason = _score_case(request, case)
        if has_free_text_query and not _case_has_relevance_evidence(request, case, score):
            continue
        scored.append((score, reason, case))

    scored.sort(key=lambda item: (-item[0], item[2].case_id))
    summaries = [
        _case_summary(case, score=round(score, 4), why_selected=reason)
        for score, reason, case in scored[: request.limit]
    ]
    return SearchPromptCasesResponse(
        cases=summaries,
        ranking_explanation=_ranking_explanation(request, summaries),
        index_version=repository.get_active_index_version(),
    )


def list_template_index() -> dict:
    cases = _sorted_template_cases()
    categories = _count_case_values(cases, lambda case: [case.category] if case.category else [])
    style_tags = _count_case_values(cases, lambda case: case.style_tags)
    use_case_tags = _count_case_values(cases, lambda case: case.use_case_tags)
    facets = _count_case_values(
        cases,
        lambda case: [case.category, *case.style_tags, *case.use_case_tags],
    )
    return {
        "total": len(cases),
        "index_version": repository.get_active_index_version(),
        "facets": facets,
        "categories": categories,
        "style_tags": style_tags,
        "use_case_tags": use_case_tags,
    }


def list_templates_page(
    *,
    category: str | None = None,
    use_case: str | None = None,
    facet: str | None = None,
    cursor: str | None = None,
    limit: int = 24,
) -> dict:
    cases = _filtered_template_cases(category=category, use_case=use_case, facet=facet)
    start = _cursor_offset(cursor)
    end = min(start + limit, len(cases))
    next_cursor = str(end) if end < len(cases) else None
    return {
        "items": [_case_summary(case, score=round(case.quality_score, 4), why_selected="template-ready case") for case in cases[start:end]],
        "total": len(cases),
        "limit": limit,
        "cursor": str(start),
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
        "index_version": repository.get_active_index_version(),
    }


def list_templates(category: str | None = None, use_case: str | None = None, limit: int = 24) -> list[PromptCaseSummary]:
    cases = _filtered_template_cases(category=category, use_case=use_case)
    return [_case_summary(case, score=round(case.quality_score, 4), why_selected="template-ready case") for case in cases[:limit]]


def _sorted_template_cases() -> list[PromptCase]:
    bootstrap_v2_repository(seed_cases=True)
    cases = repository.list_cases(active_only=True)
    cases.sort(key=lambda case: (-case.quality_score, case.category, case.title, case.case_id))
    return cases


def _filtered_template_cases(
    *,
    category: str | None = None,
    use_case: str | None = None,
    facet: str | None = None,
) -> list[PromptCase]:
    cases = _sorted_template_cases()
    if category:
        cases = [case for case in cases if case.category == category]
    if use_case:
        cases = [case for case in cases if use_case in case.use_case_tags]
    normalized_facet = (facet or "").strip()
    if normalized_facet and normalized_facet != "all":
        cases = [case for case in cases if _case_has_facet(case, normalized_facet)]
    return cases


def _case_has_facet(case: PromptCase, facet: str) -> bool:
    return facet in {case.category, *case.style_tags, *case.use_case_tags}


def _count_case_values(cases: list[PromptCase], values_for_case) -> list[dict[str, int | str]]:
    counts: Counter[str] = Counter()
    for case in cases:
        for value in set(values_for_case(case)):
            if value:
                counts[str(value)] += 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _cursor_offset(cursor: str | None) -> int:
    try:
        return max(0, int(str(cursor or "0")))
    except (TypeError, ValueError):
        return 0


def get_prompt_case(case_id: str) -> PromptCase | None:
    bootstrap_v2_repository(seed_cases=True)
    return repository.get_case(case_id)


def _excluded_by_risk(risk_filters: list[str], case: PromptCase) -> bool:
    if not risk_filters:
        return False
    risk_tags = set(case.risk_tags)
    if "exclude_portrait_authorization" in risk_filters and "requires_portrait_authorization" in risk_tags:
        return True
    if "exclude_protected_ip" in risk_filters and "avoid_protected_character_similarity" in risk_tags:
        return False
    if "exclude_unlicensed_logo" in risk_filters and "avoid_real_brand_copying" in risk_tags:
        return False
    return False


def _score_case(request: SearchPromptCasesRequest, case: PromptCase) -> tuple[float, str]:
    query_text = _expanded_query_text(request.query_text)
    query_counter = Counter(_tokens(query_text))
    case_text = _case_search_text(case)
    case_counter = Counter(_tokens(case_text))
    overlap = sum((query_counter & case_counter).values())
    semantic = overlap / max(1, sum(query_counter.values()))
    substring_match = _substring_match_score(request.query_text, case_text)
    query_features = _query_feature_tags(request.query_text)
    case_features = _case_feature_tags(case)
    feature_hits = query_features.intersection(case_features)
    feature_match = len(feature_hits) / max(1, len(query_features)) if query_features else 0.0
    subject_title_match = _specific_subject_title_match(query_features, case)
    profile_score = _profile_quality_score(case)
    style_match = 1.0 if set(request.style_filters).intersection(case.style_tags) else 0.0
    use_case_match = 1.0 if set(request.use_case_filters).intersection(case.use_case_tags) else 0.0
    category_match = 1.0 if request.category_filters and case.category in request.category_filters else 0.0
    if not request.category_filters:
        category_match = 0.5
    score = (
        semantic * 0.22
        + feature_match * 0.27
        + subject_title_match * 0.08
        + substring_match * 0.08
        + style_match * 0.12
        + use_case_match * 0.12
        + category_match * 0.05
        + profile_score * 0.05
        + case.quality_score * 0.06
    )
    reasons: list[str] = []
    if feature_hits:
        labels = ", ".join(_feature_label(feature) for feature in sorted(feature_hits)[:5])
        reasons.append(f"feature tag match / case profile match {len(feature_hits)}/{len(query_features)}: {labels}")
    if subject_title_match:
        reasons.append("primary subject title/summary match")
    if semantic > 0:
        reasons.append("semantic prompt overlap")
    if substring_match > 0:
        reasons.append("fuzzy text match")
    if style_match:
        reasons.append("style filter match")
    if use_case_match:
        reasons.append("use-case match")
    if category_match >= 1:
        reasons.append("category match")
    if profile_score:
        reasons.append(f"profile depth {profile_score:.2f}")
    reasons.append(f"quality {case.quality_score:.2f}")
    return score, ", ".join(reasons)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _case_matches_free_text_query(request: SearchPromptCasesRequest, case: PromptCase) -> bool:
    query_features = _query_feature_tags(request.query_text)
    if query_features:
        case_features = _case_feature_tags(case)
        feature_hits = query_features.intersection(case_features)
        specific_subject_features = _query_specific_subject_features(query_features)
        core_subject_features = specific_subject_features.intersection(CORE_SUBJECT_FEATURES)
        if core_subject_features and not _core_subjects_satisfied(core_subject_features, case_features):
            return False
        if not core_subject_features and specific_subject_features and not specific_subject_features.intersection(case_features):
            return False
        required_feature_hits = 1
        if len(query_features) >= 6:
            required_feature_hits = 3
        elif len(query_features) >= 3:
            required_feature_hits = 2
        elif len(query_features) >= 2:
            required_feature_hits = 2
        return len(feature_hits) >= required_feature_hits
    query_tokens = set(_tokens(_expanded_query_text(request.query_text)))
    if not query_tokens:
        normalized_query = request.query_text.strip().lower()
        if not normalized_query:
            return True
        if _contains_cjk(normalized_query):
            return normalized_query in _case_base_text(case).lower()
        return False
    case_tokens = set(_tokens(_case_search_text(case)))
    specific_tokens = {token for token in query_tokens if token not in GENERIC_QUERY_TOKENS and len(token) > 2}
    if specific_tokens:
        required_specific_hits = 1
        if len(specific_tokens) >= 5:
            required_specific_hits = 3
        elif len(specific_tokens) >= 3:
            required_specific_hits = 2
        return len(specific_tokens.intersection(case_tokens)) >= required_specific_hits
    required_hits = min(3, max(1, len(query_tokens) // 2))
    return len(query_tokens.intersection(case_tokens)) >= required_hits


def _case_has_relevance_evidence(request: SearchPromptCasesRequest, case: PromptCase, score: float) -> bool:
    if _case_matches_free_text_query(request, case):
        return True
    if _query_specific_subject_features(_query_feature_tags(request.query_text)):
        return False
    expanded_query_tokens = {
        token for token in _tokens(_expanded_query_text(request.query_text)) if token not in GENERIC_QUERY_TOKENS and len(token) > 2
    }
    if expanded_query_tokens and expanded_query_tokens.intersection(_tokens(_case_search_text(case))) and score >= MIN_FREE_TEXT_RELEVANCE_SCORE:
        return True
    return score >= MIN_FREE_TEXT_RELEVANCE_SCORE


def _expanded_query_text(text: str) -> str:
    expansions: list[str] = []
    for marker, words in QUERY_EXPANSIONS.items():
        if marker in text:
            expansions.extend(words)
    return " ".join([text, *expansions])


def _case_search_text(case: PromptCase) -> str:
    cache_key = _case_profile_cache_key(case)
    cached = _CASE_SEARCH_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    profile = build_case_profile(case)
    text = " ".join(
        [
            _case_base_text(case),
            " ".join(sorted(_case_feature_tags(case))),
            " ".join(profile.subject_tags),
            " ".join(profile.style_tags),
            " ".join(profile.use_case_tags),
            " ".join(profile.material_tags),
            " ".join(profile.color_tags),
            " ".join(profile.lighting_tags),
            " ".join(profile.composition_tags),
            " ".join(profile.reusable_principles),
            " ".join(profile.suitable_for),
        ]
    )
    _CASE_SEARCH_TEXT_CACHE[cache_key] = text
    return text


def _case_base_text(case: PromptCase) -> str:
    cache_key = _case_cache_key(case)
    cached = _CASE_BASE_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    text = " ".join(
        [
            case.title,
            case.summary,
            case.category,
            case.raw_prompt,
            " ".join(case.style_tags),
            " ".join(case.use_case_tags),
            " ".join(case.risk_tags),
            " ".join(str(value) for value in case.prompt_atoms.values()),
            " ".join(str(value) for value in case.visual_features.values()),
        ]
    )
    _CASE_BASE_TEXT_CACHE[cache_key] = text
    return text


def _query_feature_tags(query_text: str) -> set[str]:
    lower = _expanded_query_text(query_text).lower()
    return {
        feature
        for feature, aliases in FEATURE_RULES.items()
        if any(_contains_alias(lower, alias) for alias in aliases["query"])
    }


def _query_specific_subject_features(query_features: set[str]) -> set[str]:
    generic_subjects = {"subject.interface", "subject.person", "subject.character"}
    return {
        feature
        for feature in query_features
        if feature.startswith("subject.") and feature not in generic_subjects
    }


def _core_subjects_satisfied(query_core_subjects: set[str], case_features: set[str]) -> bool:
    for feature in query_core_subjects:
        accepted = CORE_SUBJECT_EQUIVALENTS.get(feature, {feature})
        if accepted.intersection(case_features):
            return True
    return False


def _specific_subject_title_match(query_features: set[str], case: PromptCase) -> float:
    specific_subjects = _query_specific_subject_features(query_features)
    if not specific_subjects:
        return 0.0
    title_text = case.title.lower()
    summary_text = case.summary.lower()
    score = 0.0
    for feature in specific_subjects:
        aliases = FEATURE_RULES.get(feature, {}).get("case", [])
        if any(_contains_alias(title_text, alias) for alias in aliases):
            score += 1.0
        elif any(_contains_alias(summary_text, alias) for alias in aliases):
            score += 0.45
    return min(1.0, score / max(1, len(specific_subjects)))


def _case_feature_tags(case: PromptCase) -> set[str]:
    cache_key = _case_cache_key(case)
    cached = _CASE_FEATURE_CACHE.get(cache_key)
    if cached is not None:
        return set(cached)
    lower = _case_base_text(case).lower()
    features = {
        feature
        for feature, aliases in FEATURE_RULES.items()
        if any(_contains_alias(lower, alias) for alias in aliases["case"])
    }
    refined = _refine_case_features(case, features)
    _CASE_FEATURE_CACHE[cache_key] = set(refined)
    return refined


def _refine_case_features(case: PromptCase, features: set[str]) -> set[str]:
    refined = set(features)
    raw_lower = case.raw_prompt.lower()
    base_lower = _case_base_text(case).lower()
    category = case.category
    if "subject.interface" in refined and category != "ui":
        if not any(_contains_alias(raw_lower, alias) for alias in ["dashboard", "interface", "saas", "app ui"]):
            refined.discard("subject.interface")
    if "tone.technology" in refined and category != "ui":
        if not any(_contains_alias(raw_lower, alias) for alias in ["technology", "futuristic", "holographic", "sci-fi"]):
            refined.discard("tone.technology")
    if "tone.medical_clean" in refined:
        if not any(_contains_alias(raw_lower, alias) for alias in ["medical", "healthcare", "clinical", "sterile"]):
            refined.discard("tone.medical_clean")
    if "subject.pet" in refined:
        if not _has_pet_subject_evidence(base_lower):
            refined.discard("subject.pet")
    if "subject.furniture" in refined:
        if not any(
            _contains_alias(base_lower, alias)
            for alias in [
                "furniture",
                "sofa",
                "couch",
                "armchair",
                "living room",
                "interior design",
                "home decor",
                "lighting fixture",
            ]
        ):
            refined.discard("subject.furniture")
    if "subject.finance" in refined:
        if not any(
            _contains_alias(base_lower, alias)
            for alias in ["finance", "bank", "banking", "fintech", "insurance"]
        ):
            refined.discard("subject.finance")
            refined.discard("use.finance")
    if "subject.education" in refined:
        if not any(
            _contains_alias(base_lower, alias)
            for alias in ["education", "course", "school", "learning", "student", "classroom", "academy"]
        ):
            refined.discard("subject.education")
            refined.discard("use.education")
    if "subject.electronics" in refined:
        if not any(
            _contains_alias(base_lower, alias)
            for alias in ["smartphone", "phone", "headphone", "earbud", "laptop", "computer", "device", "electronics"]
        ):
            refined.discard("subject.electronics")
    if "subject.bag_accessory" in refined:
        if not any(_contains_alias(base_lower, alias) for alias in ["handbag", "purse", "tote", "backpack", "bag"]):
            refined.discard("subject.bag_accessory")
    if "subject.travel_city" in refined:
        if not any(
            _contains_alias(base_lower, alias)
            for alias in ["travel", "tourism", "destination", "city", "urban", "map", "landmark"]
        ):
            refined.discard("subject.travel_city")
            refined.discard("use.travel")
    return refined


def _has_pet_subject_evidence(lower_text: str) -> bool:
    if any(_contains_alias(lower_text, alias) for alias in ["pet", "puppy", "kitten", "animal companion"]):
        return True
    has_cat = re.search(r"(?<![a-z0-9])cat(?!-?(eye|ear|eared))(?![a-z0-9])", lower_text) is not None
    has_dog = re.search(r"(?<!hot )(?<![a-z0-9])dog(?![a-z0-9])", lower_text) is not None
    return has_cat or has_dog


def _contains_alias(lower_text: str, alias: str) -> bool:
    normalized = alias.lower().strip()
    if not normalized:
        return False
    if re.search(r"[\u4e00-\u9fff]", normalized):
        return normalized in lower_text
    if re.fullmatch(r"[a-z0-9]+", normalized):
        return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", lower_text) is not None
    return normalized in lower_text


def _contains_cjk(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text or "") is not None


def build_case_profile(case: PromptCase) -> CaseProfile:
    cache_key = _case_profile_cache_key(case)
    cached = _CASE_PROFILE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    feature_tags = sorted(_case_feature_tags(case))
    atoms = case.prompt_atoms or {}
    visual = case.visual_features or {}
    visual_signals = build_case_visual_signals(case)
    stored_profile = visual.get("case_profile") if isinstance(visual.get("case_profile"), dict) else {}
    stored_source = stored_profile.get("source")
    source = stored_source if stored_source in {"rules", "claude-code"} else "rules"
    model = stored_profile.get("model") or settings.case_intelligence_model or _case_intelligence_default_model(
        settings.case_intelligence_provider
    )
    profile = CaseProfile(
        source=source,  # type: ignore[arg-type]
        model=model,
        subject_tags=_group_feature_labels(feature_tags, "subject"),
        style_tags=_dedupe_strings(
            [
                *_group_feature_labels(feature_tags, "tone"),
                *_group_feature_labels(feature_tags, "style"),
                *_case_style_tags_for_profile(case),
                *visual_signals.style_tags,
            ]
        ),
        use_case_tags=_dedupe_strings(
            [*_group_feature_labels(feature_tags, "use"), *_case_use_case_tags_for_profile(case), _category_label(case.category)]
        ),
        material_tags=_dedupe_strings([*_group_feature_labels(feature_tags, "material"), *visual_signals.material_tags]),
        color_tags=_dedupe_strings([*_group_feature_labels(feature_tags, "color"), *visual_signals.color_tags]),
        lighting_tags=_group_feature_labels(feature_tags, "lighting"),
        composition_tags=_group_feature_labels(feature_tags, "composition"),
        reusable_principles=_dedupe_strings(
            [
                *_value_list(stored_profile.get("reusable_principles")),
                *visual_signals.reusable_principles,
                visual_signals.brief,
                *_atom_values(atoms, ["composition", "lighting", "color_palette", "material_texture", "mood", "typography"]),
            ]
        )[:8],
        suitable_for=_dedupe_strings(
            [
                *_value_list(stored_profile.get("suitable_for")),
                *case.use_case_tags,
                _category_label(case.category),
            ]
        ),
        caution_tags=_dedupe_strings([*case.risk_tags, *_value_list(stored_profile.get("caution_tags"))]),
    )
    _CASE_PROFILE_CACHE[cache_key] = profile
    return profile


def _case_cache_key(case: PromptCase) -> tuple[str, str]:
    return case.case_id, case.index_version


def _case_profile_cache_key(case: PromptCase) -> tuple[str, str, str, str | None]:
    return (
        case.case_id,
        case.index_version,
        settings.case_intelligence_provider,
        settings.case_intelligence_model,
    )


def _profile_quality_score(case: PromptCase) -> float:
    features = _case_feature_tags(case)
    axes = {feature.split(".", 1)[0] for feature in features}
    atom_count = len([value for value in (case.prompt_atoms or {}).values() if str(value).strip()])
    return min(1.0, (len(axes) * 0.12) + (min(atom_count, 8) * 0.035))


def _group_feature_labels(features: list[str], prefix: str) -> list[str]:
    return [_feature_label(feature) for feature in features if feature.startswith(f"{prefix}.")]


def _feature_label(feature: str) -> str:
    return FEATURE_LABELS_ZH.get(feature, feature)


def _case_intelligence_default_model(source: str) -> str | None:
    if source == "claude-code":
        return settings.claude_orchestrator_model or "Claude Code 默认模型"
    return None


def _case_style_tags_for_profile(case: PromptCase) -> list[str]:
    if case.category == "ui":
        return case.style_tags
    return [tag for tag in case.style_tags if tag != "ui"]


def _case_use_case_tags_for_profile(case: PromptCase) -> list[str]:
    if case.category == "ui":
        return case.use_case_tags
    return [tag for tag in case.use_case_tags if tag != "ui"]


def _category_label(category: str) -> str:
    labels = {
        "ad-creative": "广告创意",
        "ecommerce": "电商主图",
        "ui": "界面设计",
        "poster": "海报",
        "portrait": "人像",
        "brand-visual": "品牌视觉",
        "social-media": "社媒",
        "character": "角色形象",
    }
    return labels.get(category, category)


def _atom_values(atoms: dict, keys: list[str]) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(_value_list(atoms.get(key)))
    return values


def _value_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _substring_match_score(query_text: str, case_text: str) -> float:
    normalized_query = query_text.strip().lower()
    normalized_case = case_text.lower()
    if not normalized_query:
        return 0.0
    markers = [
        marker
        for marker in [normalized_query, *_expanded_query_text(normalized_query).split()]
        if marker not in GENERIC_QUERY_TOKENS
    ]
    hits = [marker for marker in markers if len(marker) >= 2 and marker in normalized_case]
    return min(1.0, len(set(hits)) / max(1, min(8, len(set(markers)))))


def _case_summary(case: PromptCase, score: float | None = None, why_selected: str | None = None) -> PromptCaseSummary:
    profile = build_case_profile(case)
    return PromptCaseSummary(
        case_id=case.case_id,
        title=case.title,
        category=case.category,
        summary=case.summary,
        preview_url=case.preview_url,
        style_tags=case.style_tags,
        use_case_tags=case.use_case_tags,
        risk_tags=case.risk_tags,
        profile_tags=_dedupe_strings(
            [
                *profile.subject_tags,
                *profile.style_tags,
                *profile.use_case_tags,
                *profile.material_tags,
                *profile.color_tags,
                *profile.lighting_tags,
                *profile.composition_tags,
            ]
        )[:10],
        score=score,
        why_selected=why_selected,
    )


def _ranking_explanation(request: SearchPromptCasesRequest, summaries: list[PromptCaseSummary]) -> str:
    if not summaries:
        return "No active cases matched the requested filters."
    return (
        f"Ranked {len(summaries)} cases by semantic overlap, use case, style filters, category fit, "
        f"quality score, and safety-friendly defaults for query: {request.query_text!r}."
    )
