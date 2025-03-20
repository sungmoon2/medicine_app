// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', function() {
    // 모양 선택 이벤트
    initShapeSelector();
    
    // 색상 선택 이벤트
    initColorSelector();
    
    // 검색 폼 이벤트
    initSearchForm();
    
    // 검색 결과 정렬 및 필터링
    initResultsFiltering();
});

// 모양 선택 기능 초기화
function initShapeSelector() {
    const shapeItems = document.querySelectorAll('.shape-item');
    const drugShapeInput = document.getElementById('drug_shape');
    
    if (!shapeItems.length || !drugShapeInput) return;
    
    shapeItems.forEach(item => {
        item.addEventListener('click', function() {
            // 이전 선택 제거
            shapeItems.forEach(el => el.classList.remove('active'));
            // 현재 선택 표시
            this.classList.add('active');
            // 숨겨진 입력 필드에 값 설정
            drugShapeInput.value = this.getAttribute('data-shape');
        });
    });
}

// 색상 선택 기능 초기화
function initColorSelector() {
    const colorItems = document.querySelectorAll('.color-item');
    const colorInput = document.getElementById('color_class1');
    
    if (!colorItems.length || !colorInput) return;
    
    colorItems.forEach(item => {
        item.addEventListener('click', function() {
            // 이전 선택 제거
            colorItems.forEach(el => el.classList.remove('active'));
            // 현재 선택 표시
            this.classList.add('active');
            // 숨겨진 입력 필드에 값 설정
            colorInput.value = this.getAttribute('data-color');
        });
    });
}

// 검색 폼 초기화
function initSearchForm() {
    const searchForm = document.querySelector('form[action="/search"]');
    
    if (!searchForm) return;
    
    // 폼 리셋 버튼 이벤트
    const resetButton = searchForm.querySelector('button[type="reset"]');
    if (resetButton) {
        resetButton.addEventListener('click', function() {
            // 모든 선택 상태 초기화
            const activeItems = searchForm.querySelectorAll('.active');
            activeItems.forEach(item => item.classList.remove('active'));
            
            // 숨겨진 입력 필드 초기화
            const hiddenInputs = searchForm.querySelectorAll('input[type="hidden"]');
            hiddenInputs.forEach(input => input.value = '');
        });
    }
    
    // 폼 제출 시 빈 매개변수 제거
    searchForm.addEventListener('submit', function(e) {
        // 폼 데이터 수집
        const formData = new FormData(this);
        
        // 빈 값 제거
        const emptyParams = [];
        for (const [key, value] of formData.entries()) {
            if (!value.trim()) {
                emptyParams.push(key);
            }
        }
        
        // 폼 제출 중지하고 필터링된 데이터로 다시 제출
        if (emptyParams.length > 0) {
            e.preventDefault();
            
            // URL 매개변수 구성
            const params = new URLSearchParams();
            for (const [key, value] of formData.entries()) {
                if (value.trim()) {
                    params.append(key, value);
                }
            }
            
            // 새 URL로 리디렉션
            window.location.href = `/search?${params.toString()}`;
        }
    });
}

// 검색 결과 정렬 및 필터링 초기화
function initResultsFiltering() {
    const sortSelect = document.getElementById('sort-results');
    
    if (!sortSelect) return;
    
    sortSelect.addEventListener('change', function() {
        // 현재 URL 매개변수 가져오기
        const urlParams = new URLSearchParams(window.location.search);
        
        // 정렬 매개변수 추가/변경
        urlParams.set('sort', this.value);
        
        // 페이지 매개변수 제거 (첫 페이지로 돌아가기)
        urlParams.delete('page');
        
        // 새 URL로 리디렉션
        window.location.href = `/search?${urlParams.toString()}`;
    });
}

// 모달 관련 함수
function openImageModal(imageUrl) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    
    if (!modal || !modalImg) return;
    
    modalImg.src = imageUrl;
    modal.style.display = 'block';
}

function closeImageModal() {
    const modal = document.getElementById('imageModal');
    if (!modal) return;
    
    modal.style.display = 'none';
}

// 무한 스크롤 구현 (추후 확장용)
/*
let page = 1;
let isLoading = false;
let hasMoreItems = true;

function loadMoreResults() {
    if (isLoading || !hasMoreItems) return;
    
    isLoading = true;
    const resultsContainer = document.getElementById('results-container');
    const loadingIndicator = document.getElementById('loading-indicator');
    
    if (!resultsContainer || !loadingIndicator) {
        isLoading = false;
        return;
    }
    
    loadingIndicator.style.display = 'block';
    
    // 현재 URL 매개변수 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('page', ++page);
    urlParams.set('format', 'json');
    
    fetch(`/search?${urlParams.toString()}`)
        .then(response => response.json())
        .then(data => {
            if (data.results.length === 0) {
                hasMoreItems = false;
                loadingIndicator.textContent = '더 이상 결과가 없습니다.';
                return;
            }
            
            // 결과 추가
            data.results.forEach(item => {
                resultsContainer.appendChild(createResultCard(item));
            });
            
            isLoading = false;
            loadingIndicator.style.display = 'none';
        })
        .catch(error => {
            console.error('Error loading more results:', error);
            isLoading = false;
            loadingIndicator.textContent = '오류가 발생했습니다. 다시 시도해주세요.';
        });
}

function createResultCard(medicine) {
    // 결과 카드 HTML 생성
    const cardDiv = document.createElement('div');
    cardDiv.className = 'col-md-4 mb-4';
    
    // 카드 내용 설정
    cardDiv.innerHTML = `
        <div class="card result-card">
            <div class="card-img-container p-3">
                ${medicine.item_image 
                    ? `<img src="${medicine.item_image}" alt="${medicine.item_name}" class="img-fluid">`
                    : `<div class="text-center text-muted">이미지 없음</div>`
                }
            </div>
            <div class="card-body">
                <h5 class="card-title">${medicine.item_name}</h5>
                <p class="card-text">
                    <small class="text-muted">${medicine.entp_name}</small>
                </p>
                <p class="card-text">
                    ${medicine.drug_shape 
                        ? `<span class="badge bg-secondary me-1">${medicine.drug_shape}</span>` 
                        : ''}
                    ${medicine.color_class1 
                        ? `<span class="badge bg-secondary me-1">${medicine.color_class1}</span>` 
                        : ''}
                </p>
                <a href="/medicine/${medicine.id}" class="btn btn-primary w-100">상세 정보</a>
            </div>
        </div>
    `;
    
    return cardDiv;
}

// 스크롤 이벤트 리스너
window.addEventListener('scroll', function() {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
        loadMoreResults();
    }
});
*/