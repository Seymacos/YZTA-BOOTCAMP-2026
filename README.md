# **Takım İsmi**

Takım 65

# Ürün İle İlgili Bilgiler

## Takım Elemanları

- Şeyma Coştur: Product Owner, Developer
- Ayşegül Kılıç: Scrum Master, Developer
- Yağmur Dedekoç : Developer
- Fırat Karataşoğlu : Developer

## Ürün İsmi

SmartFinance — Kişisel Finans & Yatırım Asistanı

## Ürün Açıklaması

- SmartFinance, kullanıcıların harcamalarını takip etmesini, kategorilere ayırmasını ve kişisel bütçe önerileri almasını sağlayan yapay zeka destekli bir finansal asistan uygulamasıdır. Kullanıcı harcamalarını manuel olarak girebilir veya banka ekstresini yükleyebilir. Sistem makine öğrenmesi ile harcamaları otomatik kategorilere ayırır, anomali tespit eder ve canlı döviz, altın, hisse verilerini takip ederek kişisel öneriler üretir.


## Ürün Özellikleri

- Harcamaları otomatik kategorilere ayırma (TF-IDF + Random Forest)
- Türkçe ve İngilizce mağaza isimlerini tanıma
- Anomali tespiti (normalden sapan harcamaları bildirme)
- Canlı döviz, altın ve hisse takibi (yfinance)
- LLM agent ile kişisel bütçe ve yatırım önerileri
- Banka ekstresi PDF okuma


## Hedef Kitle

- Kişisel bütçesini takip etmek isteyen bireyler
- Yatırım kararlarını veriye dayandırmak isteyenler
- Aylık harcamalarını analiz etmek isteyen çalışanlar ve öğrenciler
- 18-65 yaş arası kullanıcılar

## Product Backlog URL

[Miro Backlog Board](https://miro.com/app/board/uXjVOSSCpsI=/)

---

# Sprint 1

- **Backlog düzeni ve Story seçimleri**: Backlog'umuz ilk yapılacak story'lere göre düzenlenmiştir. Sprint başına tahmin edilen puan sayısını geçmeyecek şekilde sıradan seçimler yapılmaktadır. Story başına çıkan tahmin puanı, toplam puanın yarısından az tutulmuştur. 

Story'ler yapılacak işlere (task'lere) bölünmüştür. Miro Board'da gözüken kırmızı item'lar yapılacak işleri (task) gösterirken, mavi item'lar story'leri temsil etmektedir.

- **Daily Scrum**: [DailyScrumMeetingSS_Sprint1.docx](https://github.com/user-attachments/files/29663753/DailyScrumMeetingSS_Sprint1.docx)


- **Sprint board update**: Sprint board screenshotları: 
<img width="616" height="335" alt="sprint1_board_baslangic" src="https://github.com/user-attachments/assets/8cb9e722-4df0-4dfd-a1d2-87802a086361" />

<img width="456" height="369" alt="sprint1_board_inprogress" src="https://github.com/user-attachments/assets/bc442537-a580-4c88-bfe9-cfa30a734f7a" />

<img width="423" height="441" alt="sprint1_board_complete" src="https://github.com/user-attachments/assets/2cd3885f-3fc4-4248-bb3c-f6f3396b499d" />


- **Ürün Durumu**: Ekran görüntüleri:
<img width="326" height="414" alt="Sprint 1 Ürünss1 " src="https://github.com/user-attachments/assets/627b6c55-77bb-4a47-b62a-4f4d589f02e0" />

<img width="325" height="481" alt="Sprint 1 Ürünss2" src="https://github.com/user-attachments/assets/1692cbf1-13c4-498e-b2b5-20de389237e1" />

<img width="324" height="337" alt="Sprint 1 Ürünss3" src="https://github.com/user-attachments/assets/359c13be-de07-4fae-b88e-cf84931fed88" />

  


- **Sprint Review**: 
Alınan kararlar: Para birimi ayrıştırması iki farklı modülde farklı şekilde ele alındığı görülmüştür. Bu tutarsızlığın tek bir standarda bağlanması bir sonraki sprint'e aktarılmıştır. Anomali tespiti özelliği, veri altyapısı hazır olmasına rağmen bu sprint kapsamına alınmamış, ilgili PBI Sprint 2'ye aktarılmıştır.
Çıkan ürünün çalışmasında ve testlerinde bir problem görülmemiştir; dashboard canlıya alınmış ve çalışan link sunulabilir durumdadır. Kategorilendirme modeli %99.66 doğrulukla test edilmiştir.
Ekstra koyulması gereken özellikler belirlenmiştir: kullanıcının kendi banka ekstresini yükleyebilmesi, anomali tespiti ve yatırımcı modu.
Sprint Review katılımcıları: Yağmur Dedekoç, Şeyma Coştur , Ayşegül Kılıç, Fırat Karataşoğlu

- **Sprint Retrospective:**
- Mock veri ile paralel çalışma yaklaşımı başarılı olmuş, ekip üyeleri birbirini beklemeden ilerleyebilmiştir; bu yöntem sonraki sprintlerde de sürdürülecektir.
- Para birimi (USD/INR) karışıklığı geç fark edilmiş, farklı modüllerde farklı çözümler üretilmiştir. Sonraki sprintte ortak kararların daha erken alınması ve modüller arası tutarlılığın planlama aşamasında netleştirilmesi gerektiği görülmüştür.
- Tahmin puanları gözden geçirilmeli; bazı işlerin (özellikle veri temizleme ve entegrasyon) tahmin edilenden daha fazla efor gerektirdiği fark edilmiştir.
