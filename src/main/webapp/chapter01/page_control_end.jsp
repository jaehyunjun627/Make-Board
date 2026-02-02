<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>page_control_end</title>
<style>
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;/*최소 화면 높이*/
    display: flex;
    align-items: center; /*세로 가운데*/
    justify-content: center;
    color: white;
}

h2 {
    text-align: center;
    font-size: 2rem;
}
</style>
</head>
<body>
	<div align ="center">
	<h2>forward action 및 sendredirect 결과</h2>
		<hr />
		지금 보여지는 화면은 page_control_end.jsp에서 출력되는 결과!!
		<hr />
		이름:<%request.getParameter("username");%>
		전화번호: <%request.getParameter("phone");%>

	</div>

</body>
</html>